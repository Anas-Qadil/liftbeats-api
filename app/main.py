from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.routes.auth import public_router as auth_public_router
from app.core.config import get_settings
from app.db import close_db_pool, open_db_pool

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_db_pool()
    yield
    close_db_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if settings.storage_backend == "local":
        settings.local_media_root_path.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.local_media_base_url,
            StaticFiles(directory=settings.local_media_root_path),
            name="media",
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    # No prefix: has to match Google's registered redirect URI exactly
    # (https://liftbeats.adintels.com/auth/callback), not /api/v1/auth/callback.
    app.include_router(auth_public_router)
    return app


app = create_app()
