"""Speech transcription of saved reels through the Anscue AI hub (anscue-ai repo).

Two entry points:
- transcribe_media(video_url, prompt): one call to the hub, returns {"text", "language"}.
- transcribe_reel(reel_id): loads the reel, calls the hub, stores the result. Used as a
  FastAPI background task after the webhook response and by the backfill script.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.db import get_pool
from app.repositories import reels

logger = logging.getLogger(__name__)

ANSCUE_AI_URL = "https://api.anscue.com"

# Whisper keeps only the last ~224 tokens of the prompt; beyond this it is wasted bytes.
PROMPT_MAX_CHARS = 600


class TranscriptionError(RuntimeError):
    pass


def is_enabled() -> bool:
    return bool(get_settings().anscue_ai_api_key)


def build_prompt(reel: dict[str, Any]) -> str | None:
    """Vocabulary hint for Whisper: the creator's handle and the caption's first line, where
    brand and product names live. Not an instruction; see the hub README."""
    parts: list[str] = []
    if reel.get("author_username"):
        parts.append(f"@{reel['author_username']}")
    if reel.get("author_name") and reel.get("author_name") != reel.get("author_username"):
        parts.append(str(reel["author_name"]))
    caption = (reel.get("caption") or "").strip()
    if caption:
        parts.append(caption.splitlines()[0].strip())
    prompt = " — ".join(p for p in parts if p)
    return prompt[:PROMPT_MAX_CHARS] or None


def _local_media_path(video_url: str) -> Path | None:
    """With the local storage backend video URLs are '/media/...' paths the hub cannot fetch,
    so we upload the file bytes instead. Returns None when the URL is not one of ours."""
    settings = get_settings()
    if settings.storage_backend != "local":
        return None
    path = urlparse(video_url).path if "://" in video_url else video_url
    base = settings.local_media_base_url.rstrip("/")
    if not path.startswith(base + "/"):
        return None
    target = (settings.local_media_root_path / path.removeprefix(base).lstrip("/")).resolve()
    root = settings.local_media_root_path
    if root != target and root not in target.parents:
        return None
    return target if target.is_file() else None


def transcribe_media(video_url: str, *, prompt: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.anscue_ai_api_key:
        raise TranscriptionError("ANSCUE_AI_API_KEY is not configured.")
    headers = {"X-API-Key": settings.anscue_ai_api_key}
    timeout = httpx.Timeout(settings.anscue_ai_timeout_seconds, connect=10.0)

    try:
        with httpx.Client(base_url=ANSCUE_AI_URL, headers=headers, timeout=timeout) as client:
            local_path = _local_media_path(video_url)
            if local_path is not None:
                with local_path.open("rb") as handle:
                    response = client.post(
                        "/v1/audio/transcriptions",
                        files={"file": (local_path.name, handle)},
                        data={"prompt": prompt} if prompt else {},
                    )
            else:
                body: dict[str, Any] = {"url": video_url}
                if prompt:
                    body["prompt"] = prompt
                response = client.post("/v1/transcriptions", json=body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise TranscriptionError(f"hub returned {exc.response.status_code}: {exc.response.text[:300]}") from exc
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"hub unreachable: {exc}") from exc

    data = response.json()
    return {"text": (data.get("text") or "").strip() or None, "language": data.get("language")}


def transcribe_reel(reel_id: int) -> bool:
    """Transcribe one reel and store the result. Never raises: failures are logged and the
    row is left untouched (transcribed_at NULL) for the backfill to retry."""
    if not is_enabled():
        return False
    try:
        with get_pool().connection() as connection:
            connection.autocommit = True
            reel = reels.get_reel(connection, reel_id)
            if reel is None or not reel.get("local_video_path"):
                return False
            result = transcribe_media(reel["local_video_path"], prompt=build_prompt(reel))
            reels.set_reel_transcript(
                connection,
                reel_id=reel_id,
                transcript=result["text"],
                language=result["language"],
            )
        logger.info("transcribed reel %s (%s, %d chars)", reel_id, result["language"], len(result["text"] or ""))
        return True
    except Exception:  # noqa: BLE001 - background work must not blow up the request or the backfill
        logger.exception("transcription of reel %s failed", reel_id)
        return False
