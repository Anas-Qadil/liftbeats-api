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


def get_user_by_google_sub(connection: PoolConnection, google_sub: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {USER_FIELDS} FROM {SCHEMA}.users WHERE google_sub = %s", (google_sub,))
        return cursor.fetchone()


def insert_google_user(
    connection: PoolConnection,
    *,
    id: str,
    google_sub: str,
    email: str | None,
    name: str | None,
    picture_url: str | None,
) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.users (id, google_sub, email, name, picture_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING {USER_FIELDS}
            """,
            (id, google_sub, email, name, picture_url),
        )
        return cursor.fetchone()


def update_google_profile(
    connection: PoolConnection,
    *,
    google_sub: str,
    email: str | None,
    name: str | None,
) -> dict[str, Any]:
    # Deliberately leaves picture_url untouched — it's set once, from our
    # own uploaded copy, the first time this google_sub ever signs in (see
    # exchange_google_code). Re-pulling Google's picture URL on every login
    # would both hotlink an unstable Google CDN link and silently overwrite
    # the copy we already own in our own storage.
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.users
            SET email = %s, name = %s
            WHERE google_sub = %s
            RETURNING {USER_FIELDS}
            """,
            (email, name, google_sub),
        )
        return cursor.fetchone()
