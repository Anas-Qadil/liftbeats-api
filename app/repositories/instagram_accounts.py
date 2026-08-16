from __future__ import annotations

from typing import Any

from app.db import PoolConnection

SCHEMA = "liftbeats"

INSTAGRAM_ACCOUNT_FIELDS = """
    id,
    user_id,
    instagram_user_id,
    username,
    created_at
"""


def get_instagram_account_by_user_id(
    connection: PoolConnection,
    user_id: str,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {INSTAGRAM_ACCOUNT_FIELDS} FROM {SCHEMA}.instagram_accounts WHERE user_id = %s",
            (user_id,),
        )
        return cursor.fetchone()


def get_instagram_account_by_instagram_user_id(
    connection: PoolConnection,
    instagram_user_id: str,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {INSTAGRAM_ACCOUNT_FIELDS}
            FROM {SCHEMA}.instagram_accounts
            WHERE instagram_user_id = %s
            """,
            (instagram_user_id,),
        )
        return cursor.fetchone()


def upsert_instagram_account(
    connection: PoolConnection,
    *,
    user_id: str,
    instagram_user_id: str,
    username: str | None,
) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.instagram_accounts (
                user_id,
                instagram_user_id,
                username
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET
                instagram_user_id = EXCLUDED.instagram_user_id,
                username = EXCLUDED.username
            RETURNING {INSTAGRAM_ACCOUNT_FIELDS}
            """,
            (user_id, instagram_user_id, username),
        )
        return cursor.fetchone()
