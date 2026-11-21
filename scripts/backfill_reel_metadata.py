"""Backfill post metadata for reels saved before it was kept.

Runs yt-dlp in metadata-only mode on each permalink, slowly, and writes
author, caption, posted_at, counts and dimensions. Rerunnable: only rows
with author_username IS NULL are touched, failures are logged and skipped.

    venv/bin/python -m scripts.backfill_reel_metadata [--limit N] [--sleep 3] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import random
import time

from app.db import close_db_pool, get_pool, open_db_pool
from app.repositories import reels
from app.services.media_ingestion import fetch_post_metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=3.0, help="seconds between permalinks, jittered")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    open_db_pool()
    done = failed = 0
    try:
        with get_pool().connection() as connection:
            # Commit each row as it lands; a pooled connection would otherwise hold
            # one transaction for the whole run and commit only at the very end.
            connection.autocommit = True
            rows = reels.list_reels_missing_metadata(connection, limit=args.limit)
            logger.info("%d reels without metadata", len(rows))
            for i, row in enumerate(rows, 1):
                url = row["source_url"]
                try:
                    meta = fetch_post_metadata(url)
                except Exception as exc:  # noqa: BLE001 - one bad permalink must not stop the run
                    failed += 1
                    logger.warning("[%d/%d] %s failed: %s", i, len(rows), url, str(exc)[:160])
                else:
                    if args.dry_run:
                        logger.info("[%d/%d] %s -> @%s %r", i, len(rows), url, meta.get("author_username"), (meta.get("caption") or "")[:60])
                    else:
                        caption = meta.pop("caption", None)
                        with connection.transaction():
                            reels.update_reel_metadata(connection, reel_id=row["id"], metadata=meta, caption=caption)
                        done += 1
                        logger.info("[%d/%d] reel %s <- @%s", i, len(rows), row["id"], meta.get("author_username"))
                if i < len(rows):
                    time.sleep(args.sleep + random.uniform(0, args.sleep))
    finally:
        close_db_pool()
    logger.info("updated %d, failed %d", done, failed)


if __name__ == "__main__":
    main()
