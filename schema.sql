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

CREATE TABLE IF NOT EXISTS liftbeats.instagram_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES liftbeats.users (id) ON DELETE CASCADE,
    instagram_user_id TEXT NOT NULL UNIQUE,
    username TEXT,
    access_token_encrypted TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ,
    granted_scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_user_id
    ON liftbeats.instagram_accounts (user_id);

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_instagram_user_id
    ON liftbeats.instagram_accounts (instagram_user_id);

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
    local_video_path TEXT NOT NULL,
    thumbnail_path TEXT,
    caption TEXT,
    platform VARCHAR(50),
    external_message_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reels_user_id
    ON liftbeats.reels (user_id);

CREATE INDEX IF NOT EXISTS idx_reels_folder_id
    ON liftbeats.reels (folder_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_reels_user_external_message_id
    ON liftbeats.reels (user_id, external_message_id)
    WHERE external_message_id IS NOT NULL;
