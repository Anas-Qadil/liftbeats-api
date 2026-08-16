from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db_connection
from app.core.config import get_settings
from app.db import PoolConnection
from app.repositories import instagram_accounts, instagram_link_codes
from app.schemas.instagram import (
    InstagramAccountRead,
    InstagramLinkCodeResponse,
    InstagramLinkStatusResponse,
)

router = APIRouter()

LINK_CODE_EXPIRE_MINUTES = 15


@router.post("/link/code", response_model=InstagramLinkCodeResponse)
def create_instagram_link_code(
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> InstagramLinkCodeResponse:
    settings = get_settings()
    user_id = str(current_user["id"])
    code = f"LB-{secrets.token_hex(3).upper()}"
    expires_at = datetime.now(UTC) + timedelta(minutes=LINK_CODE_EXPIRE_MINUTES)

    with connection.transaction():
        instagram_link_codes.delete_codes_for_user(connection, user_id)
        instagram_link_codes.create_link_code(
            connection,
            code=code,
            user_id=user_id,
            expires_at=expires_at,
        )

    deep_link = f"https://ig.me/m/{settings.instagram_business_username}?text={quote(code)}"
    return InstagramLinkCodeResponse(code=code, deep_link=deep_link, expires_at=expires_at)


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
