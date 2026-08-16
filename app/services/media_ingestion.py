from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx
import yt_dlp

from app.core.config import get_settings
from app.db import PoolConnection
from app.repositories import instagram_accounts, instagram_link_codes, reels
from app.services.storage import LocalStorageService, S3StorageService
from app.services.thumbnail import generate_thumbnail

logger = logging.getLogger(__name__)

SUPPORTED_ATTACHMENT_TYPES = {"ig_reel", "reel", "video", "share"}


class MediaIngestionService:
    def __init__(
        self,
        connection: PoolConnection,
        storage_service: LocalStorageService | S3StorageService,
    ) -> None:
        self.connection = connection
        self.storage_service = storage_service
        self.settings = get_settings()

    def process_instagram_webhook(self, payload: dict) -> int:
        processed_count = 0

        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                processed_count += self._process_event(event)

        return processed_count

    def _process_event(self, event: dict) -> int:
        message = event.get("message") or {}
        if message.get("is_echo") or message.get("is_self") or message.get("is_deleted"):
            return 0

        sender_id = str((event.get("sender") or {}).get("id") or "")
        if not sender_id:
            return 0

        text = (message.get("text") or "").strip()
        if text and self._try_consume_link_code(sender_id, text):
            return 0

        external_message_id = message.get("mid")
        if not external_message_id:
            return 0

        linked_account = instagram_accounts.get_instagram_account_by_instagram_user_id(
            self.connection,
            sender_id,
        )
        if linked_account is None:
            return 0

        existing_reel = reels.get_reel_by_external_message_id(
            self.connection,
            user_id=str(linked_account["user_id"]),
            external_message_id=external_message_id,
        )
        if existing_reel is not None:
            return 0

        media_info = self._extract_media_info(message)
        if media_info is None:
            return 0

        # Dedup by the reel itself, not just the DM message id — the same
        # reel shared in two separate messages (different external_message_id
        # each time) shouldn't create two rows.
        existing_by_source = reels.get_reel_by_source_url(
            self.connection,
            user_id=str(linked_account["user_id"]),
            source_url=media_info["source_url"],
        )
        if existing_by_source is not None:
            return 0

        video_url = None
        thumbnail_url = None
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                downloaded_video, cover_thumbnail = self._download_media(media_info["source_url"], tmp_path)
                video_url = self.storage_service.store_file(
                    downloaded_video,
                    user_id=str(linked_account["user_id"]),
                    kind="reels",
                )

                thumbnail_path = cover_thumbnail or generate_thumbnail(downloaded_video, tmp_path)
                if thumbnail_path is not None:
                    thumbnail_url = self.storage_service.store_file(
                        thumbnail_path,
                        user_id=str(linked_account["user_id"]),
                        kind="thumbnails",
                    )
        except Exception:  # pragma: no cover - defensive logging around network/media failures
            # Still save the reel with just its source_url — a retry pass
            # can pick up any row with local_video_path IS NULL later,
            # rather than losing track of the share entirely.
            logger.exception("Failed to download Instagram media; saving source_url for retry.")

        reels.create_reel(
            self.connection,
            user_id=str(linked_account["user_id"]),
            folder_id=None,
            source_url=media_info["source_url"],
            local_video_path=video_url,
            thumbnail_path=thumbnail_url,
            caption=message.get("text") or media_info.get("caption"),
            platform="instagram",
            external_message_id=external_message_id,
        )
        return 1

    def _try_consume_link_code(self, sender_id: str, text: str) -> bool:
        code = text.upper()
        link_code = instagram_link_codes.get_active_link_code(self.connection, code)
        if link_code is None:
            return False

        instagram_accounts.upsert_instagram_account(
            self.connection,
            user_id=str(link_code["user_id"]),
            instagram_user_id=sender_id,
            username=None,
        )
        instagram_link_codes.delete_link_code(self.connection, code)
        return True

    def _extract_media_info(self, message: dict) -> dict[str, str | None] | None:
        for attachment in message.get("attachments", []):
            attachment_type = str(attachment.get("type") or "").lower()
            if attachment_type not in SUPPORTED_ATTACHMENT_TYPES:
                continue

            payload = attachment.get("payload") or {}
            source_url = payload.get("url")
            if not source_url:
                continue

            return {
                "source_url": source_url,
                "caption": attachment.get("title"),
            }

        return None

    def _download_media(self, url: str, output_dir: Path) -> tuple[Path, Path | None]:
        # Meta's messaging webhook only ever gives us the post's permalink,
        # not a direct video file (confirmed by inspecting a real payload —
        # downloading that URL directly returns the Instagram webpage, not
        # a video). yt-dlp resolves the permalink to the actual asset, and
        # also gives us Instagram's own cover image (info["thumbnail"]) —
        # far more representative than a frame we'd grab ourselves, which
        # tends to land on a black intro/title card.
        outtmpl = str(output_dir / "reel.%(ext)s")
        ydl_opts = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = Path(ydl.prepare_filename(info))

        thumbnail_path = None
        thumbnail_url = info.get("thumbnail")
        if thumbnail_url:
            try:
                with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
                    response = client.get(thumbnail_url)
                    response.raise_for_status()
                thumbnail_path = output_dir / "cover.jpg"
                thumbnail_path.write_bytes(response.content)
            except Exception:
                logger.exception("Failed to download Instagram's cover image; falling back to a captured frame.")
                thumbnail_path = None

        return video_path, thumbnail_path
