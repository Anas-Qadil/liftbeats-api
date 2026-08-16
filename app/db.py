from __future__ import annotations

from collections.abc import Generator
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings

PoolConnection = Connection[dict[str, Any]]

_pool: ConnectionPool | None = None


def open_db_pool() -> None:
    global _pool
    if _pool is not None:
        return

    settings = get_settings()
    _pool = ConnectionPool(
        conninfo=settings.database_url,
        kwargs={"row_factory": dict_row},
        min_size=1,
        max_size=10,
        open=True,
    )


def close_db_pool() -> None:
    global _pool
    if _pool is None:
        return
    _pool.close()
    _pool = None


def get_connection() -> Generator[PoolConnection, None, None]:
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")

    with _pool.connection() as connection:
        yield connection


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    return _pool
