from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import PoolConnection

SCHEMA = "liftbeats"


def create_link_code(
    connection: PoolConnection,
    *,
    code: str,
    user_id: str,
    expires_at: datetime,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.instagram_link_codes (code, user_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (code, user_id, expires_at),
        )


def delete_codes_for_user(connection: PoolConnection, user_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {SCHEMA}.instagram_link_codes WHERE user_id = %s",
            (user_id,),
        )


def get_active_link_code(connection: PoolConnection, code: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT code, user_id, expires_at
            FROM {SCHEMA}.instagram_link_codes
            WHERE code = %s AND expires_at > NOW()
            """,
            (code,),
        )
        return cursor.fetchone()


def delete_link_code(connection: PoolConnection, code: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {SCHEMA}.instagram_link_codes WHERE code = %s",
            (code,),
        )
