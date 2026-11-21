-- Post metadata on reels. Safe to run on a live database: nullable columns only.
ALTER TABLE liftbeats.reels
    ADD COLUMN IF NOT EXISTS author_username TEXT,
    ADD COLUMN IF NOT EXISTS author_name TEXT,
    ADD COLUMN IF NOT EXISTS posted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS like_count INTEGER,
    ADD COLUMN IF NOT EXISTS comment_count INTEGER,
    ADD COLUMN IF NOT EXISTS width INTEGER,
    ADD COLUMN IF NOT EXISTS height INTEGER;
