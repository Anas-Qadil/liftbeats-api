"""Transcribe reels that have a stored video but no transcript yet.

Covers reels saved before transcription existed and any whose background
transcription failed (hub down, timeout). Rerunnable: only rows with
transcribed_at IS NULL are touched; failures are logged and left for next time.

    venv/bin/python -m scripts.backfill_transcripts [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging

from app.db import close_db_pool, get_pool, open_db_pool
from app.repositories import reels
from app.services.transcription import is_enabled, transcribe_reel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not is_enabled():
        raise SystemExit("ANSCUE_AI_API_KEY is empty; nothing to do.")

    open_db_pool()
    done = failed = 0
    try:
        with get_pool().connection() as connection:
            rows = reels.list_reels_missing_transcript(connection, limit=args.limit)
        logger.info("%d reels without transcript", len(rows))
        for i, row in enumerate(rows, 1):
            if args.dry_run:
                logger.info("[%d/%d] would transcribe reel %s (%s)", i, len(rows), row["id"], row["local_video_path"])
                continue
            # Sequential on purpose: the hub runs one inference at a time, so parallel
            # requests would just queue there and risk timeouts.
            if transcribe_reel(row["id"]):
                done += 1
            else:
                failed += 1
            logger.info("[%d/%d] reel %s done=%d failed=%d", i, len(rows), row["id"], done, failed)
    finally:
        close_db_pool()
    logger.info("finished: %d transcribed, %d failed", done, failed)


if __name__ == "__main__":
    main()
