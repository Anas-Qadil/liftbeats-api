from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from typing import Any

from app.api.deps import get_current_user, get_db_connection
from app.core.config import get_settings
from app.core.security import create_access_token, create_google_oauth_state_token, decode_google_oauth_state_token
from app.db import PoolConnection
from app.repositories import users
from app.schemas.auth import (
    GoogleCodeExchangeRequest,
    GoogleLoginResponse,
    TokenResponse,
    UserRead,
)
from app.services.google_auth import GoogleAuthService

router = APIRouter()


@router.get("/google/login", response_model=GoogleLoginResponse)
def google_login(
    redirect_uri: str = Query(..., description="Frontend callback URI registered in Google OAuth."),
) -> GoogleLoginResponse:
    auth_service = GoogleAuthService()
    state = create_google_oauth_state_token(redirect_uri)

    try:
        authorization_url = auth_service.build_authorization_url(redirect_uri=redirect_uri, state=state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return GoogleLoginResponse(authorization_url=authorization_url, state=state)


@router.post("/google/exchange", response_model=TokenResponse)
def exchange_google_code(
    payload: GoogleCodeExchangeRequest,
    connection: PoolConnection = Depends(get_db_connection),
) -> TokenResponse:
    state_payload = decode_google_oauth_state_token(payload.state)
    expected_redirect_uri = state_payload.get("redirect_uri")
    if expected_redirect_uri != payload.redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redirect URI does not match the issued state token.",
        )

    auth_service = GoogleAuthService()
    try:
        google_identity = auth_service.exchange_code(
            code=payload.code,
            redirect_uri=payload.redirect_uri,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google code exchange failed: {exc}",
        ) from exc

    with connection.transaction():
        user = users.upsert_google_user(
            connection,
            google_sub=google_identity.google_sub,
            email=google_identity.email,
            name=google_identity.name,
            picture_url=google_identity.picture_url,
        )

    access_token = create_access_token(str(user["id"]))
    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().jwt_access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(current_user)
