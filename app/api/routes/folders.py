from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_user, get_db_connection
from app.db import PoolConnection
from app.repositories import folders
from app.schemas.folders import FolderCreate, FolderRead, FolderUpdate

router = APIRouter()


@router.get("", response_model=list[FolderRead])
def list_user_folders(
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[FolderRead]:
    records = folders.list_folders(connection, str(current_user["id"]))
    return [FolderRead.model_validate(record) for record in records]


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_user_folder(
    payload: FolderCreate,
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> FolderRead:
    with connection.transaction():
        record = folders.create_folder(
            connection,
            user_id=str(current_user["id"]),
            name=payload.name.strip(),
        )
    return FolderRead.model_validate(record)


@router.patch("/{folder_id}", response_model=FolderRead)
def rename_user_folder(
    folder_id: int,
    payload: FolderUpdate,
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> FolderRead:
    with connection.transaction():
        record = folders.rename_folder(
            connection,
            user_id=str(current_user["id"]),
            folder_id=folder_id,
            name=payload.name.strip(),
        )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
    return FolderRead.model_validate(record)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_folder(
    folder_id: int,
    connection: PoolConnection = Depends(get_db_connection),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    with connection.transaction():
        deleted = folders.delete_folder(
            connection,
            user_id=str(current_user["id"]),
            folder_id=folder_id,
        )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
