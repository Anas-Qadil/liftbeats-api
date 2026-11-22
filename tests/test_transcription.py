from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.transcription import PROMPT_MAX_CHARS, _local_media_path, build_prompt


def test_build_prompt_uses_handle_name_and_first_caption_line() -> None:
    reel = {"author_username": "nike", "author_name": "Nike", "caption": "Just Do It.\nsecond line"}
    assert build_prompt(reel) == "@nike — Nike — Just Do It."


def test_build_prompt_skips_duplicate_name_and_empty_fields() -> None:
    assert build_prompt({"author_username": "nike", "author_name": "nike", "caption": None}) == "@nike"
    assert build_prompt({}) is None


def test_build_prompt_is_capped() -> None:
    assert len(build_prompt({"caption": "x" * 5000}) or "") == PROMPT_MAX_CHARS


def test_local_media_path_resolves_inside_media_root(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "local_media_root", str(tmp_path))
    monkeypatch.setattr(settings, "local_media_base_url", "/media")
    video = tmp_path / "reels" / "u1" / "clip.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x")

    assert _local_media_path("/media/reels/u1/clip.mp4") == video
    assert _local_media_path("http://localhost:8000/media/reels/u1/clip.mp4") == video
    assert _local_media_path("/media/reels/u1/missing.mp4") is None
    assert _local_media_path("/media/../etc/passwd") is None
    assert _local_media_path("https://assets.adintels.com/reels/u1/clip.mp4") is None
