from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token
from app.db import PoolConnection, get_connection
from app.repositories import users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/google/exchange")


def get_db_connection(connection: PoolConnection = Depends(get_connection)) -> PoolConnection:
    return connection


def get_current_user(
    connection: PoolConnection = Depends(get_db_connection),
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    payload = decode_access_token(token)
    user = users.get_user_by_id(connection, payload.sub)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
        )
    return user
