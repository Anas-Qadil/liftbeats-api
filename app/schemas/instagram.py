from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InstagramLinkStartResponse(BaseModel):
    authorization_url: str
    state: str


class InstagramAccountRead(BaseModel):
    id: UUID
    user_id: UUID
    instagram_user_id: str
    username: str | None
    token_expires_at: datetime | None
    granted_scopes: list[str]
    created_at: datetime


class InstagramLinkStatusResponse(BaseModel):
    linked: bool
    account: InstagramAccountRead | None
