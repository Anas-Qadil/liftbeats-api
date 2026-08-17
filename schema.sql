CREATE SCHEMA IF NOT EXISTS liftbeats;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS liftbeats.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub TEXT NOT NULL UNIQUE,
    email TEXT,
    name TEXT,
    picture_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email
    ON liftbeats.users (email);

-- Opaque, DB-backed refresh tokens (see app/core/security.py's
-- generate_refresh_token) — only the sha256 hash is ever stored, so a DB
-- leak doesn't hand out usable tokens. Rotated on every use and revocable
-- (logout, or automatically on reuse-after-rotation), unlike the JWT
-- access token itself.
CREATE TABLE IF NOT EXISTS liftbeats.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES liftbeats.users (id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
    ON liftbeats.refresh_tokens (user_id);

CREATE TABLE IF NOT EXISTS liftbeats.instagram_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES liftbeats.users (id) ON DELETE CASCADE,
    instagram_user_id TEXT NOT NULL UNIQUE,
    username TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_user_id
    ON liftbeats.instagram_accounts (user_id);

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_instagram_user_id
    ON liftbeats.instagram_accounts (instagram_user_id);

-- One-time codes a user sends by DM to prove a given Instagram sender_id
-- (of any account type) belongs to them, without going through Meta OAuth.
CREATE TABLE IF NOT EXISTS liftbeats.instagram_link_codes (
    code TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES liftbeats.users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_instagram_link_codes_user_id
    ON liftbeats.instagram_link_codes (user_id);

CREATE TABLE IF NOT EXISTS liftbeats.folders (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES liftbeats.users (id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_folders_user_id
    ON liftbeats.folders (user_id);

CREATE TABLE IF NOT EXISTS liftbeats.reels (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES liftbeats.users (id) ON DELETE CASCADE,
    folder_id BIGINT REFERENCES liftbeats.folders (id) ON DELETE SET NULL,
    source_url TEXT,
    local_video_path TEXT,
    thumbnail_path TEXT,
    caption TEXT,
    platform VARCHAR(50),
    external_message_id TEXT,
    -- Bumped whenever local_video_path's target file actually changes (see
    -- set_reel_media) — clients cache the video locally and compare this
    -- to decide whether to re-download rather than trusting local_video_path
    -- alone, which never changes.
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reels_user_id
    ON liftbeats.reels (user_id);

CREATE INDEX IF NOT EXISTS idx_reels_folder_id
    ON liftbeats.reels (folder_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_reels_user_external_message_id
    ON liftbeats.reels (user_id, external_message_id)
    WHERE external_message_id IS NOT NULL;
