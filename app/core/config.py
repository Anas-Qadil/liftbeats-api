from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lift Beats API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    app_base_url: str = "https://liftbeats.adintels.com"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "liftbeats"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    google_client_id: str = Field(default="", validation_alias="CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="CLIENT_SECRET")
    google_mobile_callback_url: str = Field(
        default="liftbeats://auth/callback",
        validation_alias="GOOGLE_MOBILE_CALLBACK_URL",
    )
    session_secret: str | None = Field(default=None, validation_alias="SESSION_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 10080
    state_token_expire_minutes: int = 10

    allowed_origins: list[str] = Field(default_factory=list)

    instagram_app_secret: str = Field(default="", validation_alias="META_APP_SECRET")
    instagram_business_username: str = "lift.beats"
    meta_webhook_verify_token: str = "change-me"

    storage_backend: Literal["local", "s3"] = "local"
    local_media_root: str = "media"
    local_media_base_url: str = "/media"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str | None = None
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""

    request_timeout_seconds: int = 30

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_csv_or_json_list(cls, value: object) -> object:
        if isinstance(value, list):
            return value
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            return json.loads(raw)
        return [part.strip() for part in raw.split(",") if part.strip()]

    @model_validator(mode="after")
    def apply_secret_defaults(self) -> "Settings":
        if not self.session_secret:
            self.session_secret = self.google_client_secret or "change-me-in-production"
        self.app_base_url = self.app_base_url.rstrip("/")
        return self

    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password)
        user = quote_plus(self.postgres_user)
        host = self.postgres_host
        port = self.postgres_port
        database = quote_plus(self.postgres_db)
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    @property
    def local_media_root_path(self) -> Path:
        return Path(self.local_media_root).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
