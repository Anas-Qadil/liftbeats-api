from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import PoolConnection

SCHEMA = "liftbeats"


def create_refresh_token(
    connection: PoolConnection,
    *,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )


def get_active_refresh_token(connection: PoolConnection, token_hash: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, user_id, token_hash, expires_at, revoked_at
            FROM {SCHEMA}.refresh_tokens
            WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > NOW()
            """,
            (token_hash,),
        )
        return cursor.fetchone()


def revoke_refresh_token(connection: PoolConnection, token_hash: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.refresh_tokens
            SET revoked_at = NOW()
            WHERE token_hash = %s AND revoked_at IS NULL
            """,
            (token_hash,),
        )
