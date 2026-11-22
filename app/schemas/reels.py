from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class ReelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    folder_id: int | None
    source_url: str | None
    local_video_path: str | None
    thumbnail_path: str | None
    caption: str | None
    platform: str | None
    external_message_id: str | None
    author_username: str | None = None
    author_name: str | None = None
    posted_at: datetime | None = None
    like_count: int | None = None
    comment_count: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    transcript: str | None = None
    transcript_language: str | None = None
    transcript_segments: list[TranscriptSegment] | None = None
    transcribed_at: datetime | None = None
    synced_at: datetime
    created_at: datetime


class MoveReelRequest(BaseModel):
    folder_id: int | None
