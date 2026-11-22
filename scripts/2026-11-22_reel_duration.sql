-- Video length in seconds from yt-dlp at ingest. Safe on a live database: nullable column only.
ALTER TABLE liftbeats.reels
    ADD COLUMN IF NOT EXISTS duration_seconds NUMERIC;
