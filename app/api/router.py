from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, folders, health, instagram, reels, webhooks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(instagram.router, prefix="/instagram", tags=["instagram"])
api_router.include_router(folders.router, prefix="/folders", tags=["folders"])
api_router.include_router(reels.router, prefix="/reels", tags=["reels"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
