from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.session_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.session_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": subject,
        "type": "access",
        "exp": expires_at,
    }
    return _encode(payload)


@dataclass(slots=True)
class NewRefreshToken:
    raw_token: str
    token_hash: str
    expires_at: datetime


def generate_refresh_token() -> NewRefreshToken:
    """Opaque, DB-backed refresh token — not a JWT, deliberately, so a
    single row can be revoked (logout, rotation on reuse) without needing a
    server-side blocklist for otherwise-stateless tokens. Only the hash is
    ever persisted (see refresh_tokens repository); the raw value is
    returned to the caller exactly once, to hand to the client.
    """
    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    return NewRefreshToken(
        raw_token=raw_token,
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> TokenPayload:
    payload = TokenPayload.model_validate(_decode(token))
    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        )
    return payload


def create_google_oauth_state_token(redirect_uri: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.state_token_expire_minutes)
    payload = {
        "type": "google_oauth_state",
        "redirect_uri": redirect_uri,
        "exp": expires_at,
    }
    return _encode(payload)


def decode_google_oauth_state_token(token: str) -> dict[str, Any]:
    payload = _decode(token)
    if payload.get("type") != "google_oauth_state":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state token.",
        )
    return payload
