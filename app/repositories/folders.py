from __future__ import annotations

from typing import Any

from app.db import PoolConnection

SCHEMA = "liftbeats"

FOLDER_FIELDS = """
    id,
    user_id,
    name,
    created_at
"""


def list_folders(connection: PoolConnection, user_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {FOLDER_FIELDS}
            FROM {SCHEMA}.folders
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        )
        return cursor.fetchall()


def create_folder(connection: PoolConnection, *, user_id: str, name: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.folders (user_id, name)
            VALUES (%s, %s)
            RETURNING {FOLDER_FIELDS}
            """,
            (user_id, name),
        )
        return cursor.fetchone()


def get_folder_by_id(
    connection: PoolConnection,
    *,
    user_id: str,
    folder_id: int,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {FOLDER_FIELDS}
            FROM {SCHEMA}.folders
            WHERE id = %s AND user_id = %s
            """,
            (folder_id, user_id),
        )
        return cursor.fetchone()


def rename_folder(
    connection: PoolConnection,
    *,
    user_id: str,
    folder_id: int,
    name: str,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.folders
            SET name = %s
            WHERE id = %s AND user_id = %s
            RETURNING {FOLDER_FIELDS}
            """,
            (name, folder_id, user_id),
        )
        return cursor.fetchone()


def delete_folder(connection: PoolConnection, *, user_id: str, folder_id: int) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {SCHEMA}.folders WHERE id = %s AND user_id = %s",
            (folder_id, user_id),
        )
        return cursor.rowcount > 0
