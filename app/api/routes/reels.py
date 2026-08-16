from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user, get_db_connection
from app.db import PoolConnection
from app.repositories import folders, reels
from app.schemas.reels import MoveReelRequest, ReelRead
from app.services.storage import get_storage_service

router = APIRouter()


@router.get("", response_model=list[ReelRead])
def list_user_reels(
    folder_id: int | None = Query(default=None),
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[ReelRead]:
    if folder_id is not None:
        folder = folders.get_folder_by_id(
            connection,
            user_id=str(current_user["id"]),
            folder_id=folder_id,
        )
        if folder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")

    records = reels.list_reels(
        connection,
        user_id=str(current_user["id"]),
        folder_id=folder_id,
    )
    return [ReelRead.model_validate(record) for record in records]


@router.patch("/{reel_id}/move", response_model=ReelRead)
def move_user_reel(
    reel_id: int,
    payload: MoveReelRequest,
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ReelRead:
    if payload.folder_id is not None:
        folder = folders.get_folder_by_id(
            connection,
            user_id=str(current_user["id"]),
            folder_id=payload.folder_id,
        )
        if folder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")

    with connection.transaction():
        record = reels.move_reel(
            connection,
            user_id=str(current_user["id"]),
            reel_id=reel_id,
            folder_id=payload.folder_id,
        )

    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found.")
    return ReelRead.model_validate(record)


@router.delete("/{reel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_reel(
    reel_id: int,
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    reel = reels.get_reel_by_id(
        connection,
        user_id=str(current_user["id"]),
        reel_id=reel_id,
    )
    if reel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found.")

    storage_service = get_storage_service()
    with connection.transaction():
        deleted = reels.delete_reel(
            connection,
            user_id=str(current_user["id"]),
            reel_id=reel_id,
        )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found.")

    storage_service.delete_file(reel.get("local_video_path"))
    storage_service.delete_file(reel.get("thumbnail_path"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
