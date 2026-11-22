-- Speech transcript on reels. Safe to run on a live database: nullable columns only.
ALTER TABLE liftbeats.reels
    ADD COLUMN IF NOT EXISTS transcript TEXT,
    ADD COLUMN IF NOT EXISTS transcript_language VARCHAR(8),
    ADD COLUMN IF NOT EXISTS transcript_segments JSONB,
    ADD COLUMN IF NOT EXISTS transcribed_at TIMESTAMPTZ;
