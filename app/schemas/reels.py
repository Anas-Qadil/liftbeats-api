from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    folder_id: int | None
    source_url: str | None
    local_video_path: str
    thumbnail_path: str | None
    caption: str | None
    platform: str | None
    external_message_id: str | None
    created_at: datetime


class MoveReelRequest(BaseModel):
    folder_id: int | None
