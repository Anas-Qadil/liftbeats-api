from __future__ import annotations

from typing import Any

from app.db import PoolConnection

SCHEMA = "liftbeats"

USER_FIELDS = """
    id,
    google_sub,
    email,
    name,
    picture_url,
    created_at
"""


def get_user_by_id(connection: PoolConnection, user_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {USER_FIELDS} FROM {SCHEMA}.users WHERE id = %s", (user_id,))
        return cursor.fetchone()


def upsert_google_user(
    connection: PoolConnection,
    *,
    google_sub: str,
    email: str | None,
    name: str | None,
    picture_url: str | None,
) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.users (google_sub, email, name, picture_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (google_sub) DO UPDATE
            SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                picture_url = EXCLUDED.picture_url
            RETURNING {USER_FIELDS}
            """,
            (google_sub, email, name, picture_url),
        )
        return cursor.fetchone()
