"""Transcribe reels that have a stored video but no transcript yet.

Covers reels saved before transcription existed and any whose background
transcription failed (hub down, timeout). Rerunnable: only rows with
transcribed_at IS NULL are touched; failures are logged and left for next time.

    venv/bin/python -m scripts.backfill_transcripts [--limit N] [--workers 4] [--missing-segments] [--dry-run]

--missing-segments also redoes reels transcribed before timestamped segments were stored.

--workers should match the hub's concurrency (GET https://api.anscue.com/health); more than
that only queues inside the hub and risks timeouts.
"""
from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor

from app.db import close_db_pool, get_pool, open_db_pool
from app.repositories import reels
from app.services.transcription import is_enabled, transcribe_reel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=1, help="parallel requests to the hub")
    parser.add_argument("--missing-segments", action="store_true", help="also redo reels that have text but no segments")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not is_enabled():
        raise SystemExit("ANSCUE_AI_API_KEY is empty; nothing to do.")

    open_db_pool()
    done = failed = 0
    try:
        with get_pool().connection() as connection:
            rows = reels.list_reels_missing_transcript(connection, limit=args.limit, missing_segments=args.missing_segments)
        logger.info("%d reels without transcript, %d worker(s)", len(rows), args.workers)
        if args.dry_run:
            for i, row in enumerate(rows, 1):
                logger.info("[%d/%d] would transcribe reel %s (%s)", i, len(rows), row["id"], row["local_video_path"])
            return
        # Each transcribe_reel takes its own pooled connection (pool max 10), so keep workers under that.
        with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
            for i, ok in enumerate(pool.map(lambda row: transcribe_reel(row["id"]), rows), 1):
                if ok:
                    done += 1
                else:
                    failed += 1
                logger.info("[%d/%d] done=%d failed=%d", i, len(rows), done, failed)
    finally:
        close_db_pool()
    logger.info("finished: %d transcribed, %d failed", done, failed)


if __name__ == "__main__":
    main()
