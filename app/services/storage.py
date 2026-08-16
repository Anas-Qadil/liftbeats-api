from __future__ import annotations

import mimetypes
import shutil
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import boto3

from app.core.config import get_settings


class LocalStorageService:
    def __init__(self) -> None:
        settings = get_settings()
        self.root = settings.local_media_root_path
        self.base_url = settings.local_media_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def store_file(self, source_path: Path, *, user_id: str, kind: str) -> str:
        suffix = source_path.suffix or mimetypes.guess_extension(
            mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        ) or ".bin"
        relative_path = Path(kind) / user_id / f"{uuid4().hex}{suffix}"
        destination = self.root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        return f"{self.base_url}/{relative_path.as_posix()}"

    def delete_file(self, file_url: str | None) -> None:
        if not file_url:
            return
        parsed = urlparse(file_url)
        path = parsed.path if parsed.scheme else file_url
        if not path.startswith(self.base_url):
            return
        relative = path.removeprefix(self.base_url).lstrip("/")
        target = (self.root / relative).resolve()
        if self.root == target or self.root in target.parents:
            target.unlink(missing_ok=True)


class S3StorageService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3.")

        self.bucket = settings.s3_bucket
        self.public_base_url = settings.s3_public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region or None,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def store_file(self, source_path: Path, *, user_id: str, kind: str) -> str:
        suffix = source_path.suffix or ".bin"
        object_key = f"{kind}/{user_id}/{uuid4().hex}{suffix}"
        content_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        with source_path.open("rb") as file_handle:
            self.client.upload_fileobj(
                file_handle,
                self.bucket,
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
        if self.public_base_url:
            return f"{self.public_base_url}/{object_key}"
        return f"s3://{self.bucket}/{object_key}"

    def delete_file(self, file_url: str | None) -> None:
        if not file_url:
            return
        if file_url.startswith(f"s3://{self.bucket}/"):
            object_key = file_url.removeprefix(f"s3://{self.bucket}/")
        elif self.public_base_url and file_url.startswith(f"{self.public_base_url}/"):
            object_key = file_url.removeprefix(f"{self.public_base_url}/")
        else:
            return
        self.client.delete_object(Bucket=self.bucket, Key=object_key)


@lru_cache
def get_storage_service() -> LocalStorageService | S3StorageService:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3StorageService()
    return LocalStorageService()
