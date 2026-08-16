from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoogleLoginResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleCodeExchangeRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    google_sub: str
    email: str | None
    name: str | None
    picture_url: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
