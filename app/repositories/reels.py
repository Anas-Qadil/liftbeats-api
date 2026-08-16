from __future__ import annotations

from typing import Any

from app.db import PoolConnection

SCHEMA = "liftbeats"

REEL_FIELDS = """
    id,
    user_id,
    folder_id,
    source_url,
    local_video_path,
    thumbnail_path,
    caption,
    platform,
    external_message_id,
    created_at
"""


def list_reels(
    connection: PoolConnection,
    *,
    user_id: str,
    folder_id: int | None = None,
) -> list[dict[str, Any]]:
    query = f"""
        SELECT {REEL_FIELDS}
        FROM {SCHEMA}.reels
        WHERE user_id = %s
    """
    params: list[Any] = [user_id]

    if folder_id is not None:
        query += " AND folder_id = %s"
        params.append(folder_id)

    query += " ORDER BY created_at DESC, id DESC"

    with connection.cursor() as cursor:
        cursor.execute(query, tuple(params))
        return cursor.fetchall()


def get_reel_by_id(
    connection: PoolConnection,
    *,
    user_id: str,
    reel_id: int,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {REEL_FIELDS}
            FROM {SCHEMA}.reels
            WHERE id = %s AND user_id = %s
            """,
            (reel_id, user_id),
        )
        return cursor.fetchone()


def get_reel_by_external_message_id(
    connection: PoolConnection,
    *,
    user_id: str,
    external_message_id: str,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {REEL_FIELDS}
            FROM {SCHEMA}.reels
            WHERE user_id = %s AND external_message_id = %s
            """,
            (user_id, external_message_id),
        )
        return cursor.fetchone()


def create_reel(
    connection: PoolConnection,
    *,
    user_id: str,
    folder_id: int | None,
    source_url: str | None,
    local_video_path: str | None,
    thumbnail_path: str | None,
    caption: str | None,
    platform: str | None,
    external_message_id: str | None,
) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.reels (
                user_id,
                folder_id,
                source_url,
                local_video_path,
                thumbnail_path,
                caption,
                platform,
                external_message_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {REEL_FIELDS}
            """,
            (
                user_id,
                folder_id,
                source_url,
                local_video_path,
                thumbnail_path,
                caption,
                platform,
                external_message_id,
            ),
        )
        return cursor.fetchone()


def set_reel_media(
    connection: PoolConnection,
    *,
    reel_id: int,
    local_video_path: str,
    thumbnail_path: str | None,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.reels
            SET local_video_path = %s, thumbnail_path = %s
            WHERE id = %s
            RETURNING {REEL_FIELDS}
            """,
            (local_video_path, thumbnail_path, reel_id),
        )
        return cursor.fetchone()


def list_reels_missing_video(connection: PoolConnection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {REEL_FIELDS}
            FROM {SCHEMA}.reels
            WHERE local_video_path IS NULL AND source_url IS NOT NULL
            ORDER BY created_at
            """
        )
        return cursor.fetchall()


def move_reel(
    connection: PoolConnection,
    *,
    user_id: str,
    reel_id: int,
    folder_id: int | None,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.reels
            SET folder_id = %s
            WHERE id = %s AND user_id = %s
            RETURNING {REEL_FIELDS}
            """,
            (folder_id, reel_id, user_id),
        )
        return cursor.fetchone()


def delete_reel(connection: PoolConnection, *, user_id: str, reel_id: int) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {SCHEMA}.reels WHERE id = %s AND user_id = %s",
            (reel_id, user_id),
        )
        return cursor.rowcount > 0
