from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InstagramAccountRead(BaseModel):
    id: UUID
    user_id: UUID
    instagram_user_id: str
    username: str | None
    created_at: datetime


class InstagramLinkStatusResponse(BaseModel):
    linked: bool
    account: InstagramAccountRead | None


class InstagramLinkCodeResponse(BaseModel):
    code: str
    deep_link: str
    expires_at: datetime
