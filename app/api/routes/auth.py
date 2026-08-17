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
from app.core.security import (
    create_access_token,
    create_google_oauth_state_token,
    decode_google_oauth_state_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.db import PoolConnection
from app.repositories import refresh_tokens, users
from app.schemas.auth import (
    GoogleCodeExchangeRequest,
    GoogleLoginResponse,
    RefreshTokenRequest,
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

    with connection.transaction():
        return _issue_tokens(connection, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    payload: RefreshTokenRequest,
    connection: PoolConnection = Depends(get_db_connection),
) -> TokenResponse:
    token_hash = hash_refresh_token(payload.refresh_token)

    with connection.transaction():
        stored = refresh_tokens.get_active_refresh_token(connection, token_hash)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid, expired, or already used.",
            )

        user = users.get_user_by_id(connection, str(stored["user_id"]))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")

        # Rotate: this token is single-use. Revoking it here means a stolen
        # refresh token can only be replayed once — the legitimate client's
        # next refresh attempt with the same (now-revoked) token fails loudly
        # instead of two parties silently sharing one session indefinitely.
        refresh_tokens.revoke_refresh_token(connection, token_hash)
        return _issue_tokens(connection, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshTokenRequest,
    connection: PoolConnection = Depends(get_db_connection),
) -> None:
    """Revokes the given refresh token server-side, so "Disconnect" in the
    app actually ends the session rather than just discarding the token
    on-device while it remains usable until it expires on its own.
    """
    with connection.transaction():
        refresh_tokens.revoke_refresh_token(connection, hash_refresh_token(payload.refresh_token))


def _issue_tokens(connection: PoolConnection, user: dict[str, Any]) -> TokenResponse:
    new_refresh_token = generate_refresh_token()
    refresh_tokens.create_refresh_token(
        connection,
        user_id=str(user["id"]),
        token_hash=new_refresh_token.token_hash,
        expires_at=new_refresh_token.expires_at,
    )
    return TokenResponse(
        access_token=create_access_token(str(user["id"])),
        refresh_token=new_refresh_token.raw_token,
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
