from __future__ import annotations

import logging
import mimetypes
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

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

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                downloaded_video = self._download_media(media_info["download_url"], tmp_path)
                video_url = self.storage_service.store_file(
                    downloaded_video,
                    user_id=str(linked_account["user_id"]),
                    kind="reels",
                )

                thumbnail_url = None
                thumbnail_path = generate_thumbnail(downloaded_video, tmp_path)
                if thumbnail_path is not None:
                    thumbnail_url = self.storage_service.store_file(
                        thumbnail_path,
                        user_id=str(linked_account["user_id"]),
                        kind="thumbnails",
                    )

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
        except Exception:  # pragma: no cover - defensive logging around network/media failures
            logger.exception("Failed to ingest Instagram media share.")
            return 0

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
            url_candidates = self._collect_urls(payload)
            if not url_candidates:
                continue

            download_url = self._pick_download_url(url_candidates)
            source_url = payload.get("url") or url_candidates[0]
            caption = attachment.get("title")

            return {
                "download_url": download_url,
                "source_url": source_url,
                "caption": caption,
            }

        return None

    def _collect_urls(self, value: object) -> list[str]:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return [value]
        if isinstance(value, dict):
            urls: list[str] = []
            for child in value.values():
                urls.extend(self._collect_urls(child))
            return urls
        if isinstance(value, list):
            urls: list[str] = []
            for child in value:
                urls.extend(self._collect_urls(child))
            return urls
        return []

    def _pick_download_url(self, urls: list[str]) -> str:
        for candidate in urls:
            lower = candidate.lower()
            if any(lower.endswith(extension) for extension in (".mp4", ".mov", ".m4v", ".webm")):
                return candidate
        return urls[0]

    def _download_media(self, url: str, output_dir: Path) -> Path:
        with httpx.Client(timeout=self.settings.request_timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        suffix = self._infer_file_suffix(url, response.headers.get("content-type"))
        destination = output_dir / f"downloaded_reel{suffix}"
        destination.write_bytes(response.content)
        return destination

    def _infer_file_suffix(self, url: str, content_type: str | None) -> str:
        if content_type:
            guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if guessed:
                return guessed

        parsed = urlparse(url)
        path = Path(parsed.path)
        if path.suffix:
            return path.suffix

        return ".mp4"
