# Lift Beats API

FastAPI backend for Lift Beats with:

- Google OAuth authentication using the same authorization-code pattern as `adintels-api`
- Instagram account linking via Meta's current Instagram login flow
- Instagram webhook ingestion for shared reels
- PostgreSQL persistence with hand-written SQL
- Local media storage for development and S3-compatible storage hooks for production

## Stack

- FastAPI
- `psycopg` connection pool
- Plain SQL repositories with the `liftbeats.` schema prefix on every query
- PostgreSQL

## Important Instagram Caveat

This scaffold uses Meta's current Instagram login flow for linking accounts and the official Instagram messaging webhook shape. As of August 16, 2026, Meta's official Instagram login/docs still revolve around Instagram professional accounts for this API surface, so confirm your app's enabled products, approved scopes, and whether your user flow is compatible with the account types you expect in production.

## Quick Start

1. Create a virtual environment and install dependencies.
2. Copy `.env.example` to `.env` and fill in your secrets.
3. Create the tables manually from [`schema.sql`](/Users/anasqadil/liftbeats-api/schema.sql).
4. Run the API:

```bash
uvicorn app.main:app --reload
```

Or just run:

```bash
make
```

## Docker

Build the image locally:

```bash
docker build -t liftbeats-api:latest .
```

Run it with Compose:

```bash
docker compose up --build
```

The compose file mounts `./media` into the container so locally stored reels/thumbnails survive container restarts.

## Database

Every table and column is `snake_case`. The schema mirrors the mobile app's folders/reels data model and adds multi-user ownership plus Instagram account linkage.

## Environment

Key settings live in `.env.example`, including:

- `APP_BASE_URL`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `CLIENT_ID`
- `CLIENT_SECRET`
- `SESSION_SECRET`
- `APP_ENCRYPTION_KEY`
- `META_APP_ID`
- `META_APP_SECRET`
- `INSTAGRAM_REDIRECT_URI`
- `META_WEBHOOK_VERIFY_TOKEN`

For the auth-only milestone, the minimum important vars are:

- `APP_BASE_URL`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `CLIENT_ID`
- `CLIENT_SECRET`
- `SESSION_SECRET`
- `ALLOWED_ORIGINS`

Production API host:

- `APP_BASE_URL=https://liftbeats.adintels.com`
- `INSTAGRAM_REDIRECT_URI=https://liftbeats.adintels.com/api/v1/instagram/link/callback`

If you configure the Meta app for Instagram linking, register that exact callback URL.

## API Overview

- `GET /api/v1/auth/google/login`
- `POST /api/v1/auth/google/exchange`
- `GET /api/v1/auth/me`
- `GET /api/v1/instagram/link/start`
- `GET /api/v1/instagram/link/callback`
- `GET /api/v1/instagram/link/status`
- `GET /api/v1/folders`
- `POST /api/v1/folders`
- `PATCH /api/v1/folders/{folder_id}`
- `DELETE /api/v1/folders/{folder_id}`
- `GET /api/v1/reels`
- `PATCH /api/v1/reels/{reel_id}/move`
- `DELETE /api/v1/reels/{reel_id}`
- `GET /api/v1/webhooks/instagram`
- `POST /api/v1/webhooks/instagram`

## CI/CD

The repo now includes a GitHub Actions workflow at [`.github/workflows/CI.yaml`](/Users/anasqadil/liftbeats-api/.github/workflows/CI.yaml) that:

- builds the Docker image on pushes to `main`
- logs in to Docker Hub using `DOCKERHUB_USER` and `DOCKERHUB_PASSWORD`
- pushes `${DOCKERHUB_USER}/liftbeats-api:latest`

Unlike the older `adintels-api` setup, runtime app secrets are not baked into the image during CI. Keep those in your deployment environment or `.env`, not in Docker build args.
