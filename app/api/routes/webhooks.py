from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from app.api.deps import get_db_connection
from app.core.config import get_settings
from app.db import PoolConnection
from app.services.media_ingestion import MediaIngestionService
from app.services.storage import get_storage_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/instagram")
def verify_instagram_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    settings = get_settings()
    if mode == "subscribe" and verify_token == settings.meta_webhook_verify_token and challenge:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed.")


@router.post("/instagram")
async def receive_instagram_webhook(
    request: Request,
    connection: PoolConnection = Depends(get_db_connection),
) -> Response:
    settings = get_settings()
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if signature and settings.instagram_app_secret:
        verify_meta_signature(raw_body, signature, settings.instagram_app_secret)

    payload = json.loads(raw_body.decode("utf-8"))
    logger.info("Instagram webhook payload: %s", json.dumps(payload))
    storage_service = get_storage_service()

    with connection.transaction():
        processed = MediaIngestionService(connection, storage_service).process_instagram_webhook(payload)

    return Response(
        content=json.dumps({"status": "accepted", "processed": processed}),
        media_type="application/json",
        status_code=status.HTTP_200_OK,
    )


def verify_meta_signature(raw_body: bytes, signature_header: str, app_secret: str) -> None:
    expected_signature = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    provided_signature = signature_header.removeprefix("sha256=")
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature.",
        )
