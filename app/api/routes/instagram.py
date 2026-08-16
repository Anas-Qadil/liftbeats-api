from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.deps import get_current_user, get_db_connection
from app.core.config import get_settings
from app.core.security import create_state_token, decode_state_token
from app.db import PoolConnection
from app.repositories import instagram_accounts
from app.schemas.instagram import (
    InstagramAccountRead,
    InstagramLinkStartResponse,
    InstagramLinkStatusResponse,
)
from app.services.instagram import InstagramOAuthService
from app.services.token_cipher import TokenCipher

router = APIRouter()


@router.get("/link/start", response_model=InstagramLinkStartResponse)
def start_instagram_link(
    redirect: bool = Query(default=False),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> InstagramLinkStartResponse | RedirectResponse:
    service = InstagramOAuthService()
    state = create_state_token(str(current_user["id"]))

    try:
        authorization_url = service.build_authorization_url(state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if redirect:
        return RedirectResponse(url=authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return InstagramLinkStartResponse(
        authorization_url=authorization_url,
        state=state,
    )


@router.get("/link/status", response_model=InstagramLinkStatusResponse)
def instagram_link_status(
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> InstagramLinkStatusResponse:
    account = instagram_accounts.get_instagram_account_by_user_id(
        connection,
        str(current_user["id"]),
    )
    if account is None:
        return InstagramLinkStatusResponse(linked=False, account=None)

    return InstagramLinkStatusResponse(
        linked=True,
        account=InstagramAccountRead.model_validate(account),
    )


@router.get("/link/callback")
def instagram_link_callback(
    code: str | None = Query(default=None),
    state_token: str | None = Query(default=None, alias="state"),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    connection: PoolConnection = Depends(get_db_connection),
) -> RedirectResponse | JSONResponse:
    settings = get_settings()

    if error:
        return _failure_redirect(error_description or error)
    if not code or not state_token:
        return _failure_redirect("Missing OAuth callback data.")

    try:
        user_id = decode_state_token(state_token)
    except HTTPException as exc:
        return _failure_redirect(exc.detail)

    service = InstagramOAuthService()
    cipher = TokenCipher()

    try:
        result = service.exchange_code(code)
    except ValueError as exc:
        return _failure_redirect(str(exc))
    except httpx.HTTPError as exc:
        return _failure_redirect(f"Instagram token exchange failed: {exc}")

    existing_account = instagram_accounts.get_instagram_account_by_instagram_user_id(
        connection,
        result.instagram_user_id,
    )
    if existing_account is not None and str(existing_account["user_id"]) != user_id:
        return _failure_redirect("That Instagram account is already linked to another Lift Beats user.")

    with connection.transaction():
        instagram_accounts.upsert_instagram_account(
            connection,
            user_id=user_id,
            instagram_user_id=result.instagram_user_id,
            username=result.username,
            access_token_encrypted=cipher.encrypt(result.access_token),
            token_expires_at=result.token_expires_at,
            granted_scopes=result.granted_scopes,
        )

    if settings.instagram_link_success_url:
        return RedirectResponse(url=settings.instagram_link_success_url, status_code=status.HTTP_302_FOUND)

    return JSONResponse({"status": "success"})


def _failure_redirect(message: str) -> RedirectResponse | JSONResponse:
    settings = get_settings()
    if settings.instagram_link_failure_url:
        query_string = urlencode({"message": message})
        return RedirectResponse(
            url=f"{settings.instagram_link_failure_url}?{query_string}",
            status_code=status.HTTP_302_FOUND,
        )
    return JSONResponse({"status": "error", "message": message}, status_code=status.HTTP_400_BAD_REQUEST)
