from __future__ import annotations

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


def decode_access_token(token: str) -> TokenPayload:
    payload = TokenPayload.model_validate(_decode(token))
    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        )
    return payload


def create_state_token(subject: str, *, expires_in_minutes: int = 15) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
    payload = {
        "sub": subject,
        "type": "instagram_link_state",
        "exp": expires_at,
    }
    return _encode(payload)


def create_google_oauth_state_token(redirect_uri: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.state_token_expire_minutes)
    payload = {
        "type": "google_oauth_state",
        "redirect_uri": redirect_uri,
        "exp": expires_at,
    }
    return _encode(payload)


def decode_state_token(token: str) -> str:
    payload = TokenPayload.model_validate(_decode(token))
    if payload.type != "instagram_link_state":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Instagram link state.",
        )
    return payload.sub


def decode_google_oauth_state_token(token: str) -> dict[str, Any]:
    payload = _decode(token)
    if payload.get("type") != "google_oauth_state":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state token.",
        )
    return payload
