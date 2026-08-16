from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class FolderUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    name: str
    created_at: datetime
