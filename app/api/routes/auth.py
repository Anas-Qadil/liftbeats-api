from __future__ import annotations

import logging
import mimetypes
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

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
from app.services.storage import LocalStorageService, S3StorageService, get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Mounted at the app root (see app/main.py) rather than under API_V1_PREFIX,
# since its path has to match the `redirect_uri` we register with Google
# exactly: https://liftbeats.adintels.com/auth/callback.
public_router = APIRouter()


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

    existing_user = users.get_user_by_google_sub(connection, google_identity.google_sub)

    if existing_user is None:
        # First-ever sign-in for this Google account: pull their profile
        # picture down and re-upload it into our own storage now, once,
        # rather than storing Google's CDN URL directly — that link isn't
        # guaranteed stable long-term, and we'd rather own a permanent copy.
        new_user_id = str(uuid4())
        picture_url = None
        if google_identity.picture_url:
            picture_url = _store_profile_picture(
                get_storage_service(),
                user_id=new_user_id,
                source_url=google_identity.picture_url,
            )
        with connection.transaction():
            user = users.insert_google_user(
                connection,
                id=new_user_id,
                google_sub=google_identity.google_sub,
                email=google_identity.email,
                name=google_identity.name,
                picture_url=picture_url,
            )
    else:
        with connection.transaction():
            user = users.update_google_profile(
                connection,
                google_sub=google_identity.google_sub,
                email=google_identity.email,
                name=google_identity.name,
            )

    access_token = create_access_token(str(user["id"]))
    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().jwt_access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


def _store_profile_picture(
    storage_service: LocalStorageService | S3StorageService,
    *,
    user_id: str,
    source_url: str,
) -> str | None:
    """Best-effort: downloads `source_url` (Google's profile picture) and
    re-uploads it into our own storage, mirroring how Instagram media gets
    ingested in MediaIngestionService. Never blocks sign-in — a failure
    here just leaves the new user without a picture_url.
    """
    settings = get_settings()
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.get(source_url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        suffix = mimetypes.guess_extension(content_type) or ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp_file:
            tmp_file.write(response.content)
            tmp_file.flush()
            return storage_service.store_file(Path(tmp_file.name), user_id=user_id, kind="avatars")
    except Exception:
        logger.exception("Failed to store Google profile picture for user %s.", user_id)
        return None


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(current_user)


@public_router.get("/auth/callback", response_model=None, include_in_schema=False)
def google_oauth_mobile_callback(request: Request) -> RedirectResponse:
    """Google's registered redirect URI has to be `https`, but the mobile
    app is actually listening for `GOOGLE_MOBILE_CALLBACK_URL` (a custom
    scheme — see AuthRepository.signInWithGoogle in the Flutter app). This
    route's only job is bouncing whatever query string Google sends
    (`code`+`state` on success, `error`(+`error_description`)+`state` if
    the user denies consent) onto that scheme, unchanged, so the app can
    catch it. No state validation or DB access here — that all happens in
    POST /google/exchange once the app calls it with the code it receives.
    """
    settings = get_settings()
    target = settings.google_mobile_callback_url
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
