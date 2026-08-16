from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings


@dataclass(slots=True)
class InstagramLinkResult:
    instagram_user_id: str
    username: str | None
    access_token: str
    token_expires_at: datetime | None
    granted_scopes: list[str]


class InstagramOAuthService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_authorization_url(self, state: str) -> str:
        if not self.settings.instagram_app_id:
            raise ValueError("META_APP_ID is not configured.")

        params = {
            "client_id": self.settings.instagram_app_id,
            "redirect_uri": self.settings.instagram_redirect_uri,
            "response_type": "code",
            "scope": ",".join(self.settings.instagram_scopes),
            "state": state,
        }
        return f"{self.settings.instagram_authorize_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> InstagramLinkResult:
        if not self.settings.instagram_app_secret:
            raise ValueError("META_APP_SECRET is not configured.")

        timeout = self.settings.request_timeout_seconds
        with httpx.Client(timeout=timeout) as client:
            short_lived_response = client.post(
                self.settings.instagram_token_url,
                data={
                    "client_id": self.settings.instagram_app_id,
                    "client_secret": self.settings.instagram_app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.settings.instagram_redirect_uri,
                    "code": code,
                },
            )
            short_lived_response.raise_for_status()
            short_lived_payload = short_lived_response.json()

            long_lived_response = client.get(
                f"{self.settings.instagram_graph_base_url}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self.settings.instagram_app_secret,
                    "access_token": short_lived_payload["access_token"],
                },
            )
            long_lived_response.raise_for_status()
            long_lived_payload = long_lived_response.json()

            profile_response = client.get(
                f"{self.settings.instagram_graph_base_url}/me",
                params={
                    "fields": "id,username,account_type",
                    "access_token": long_lived_payload["access_token"],
                },
            )
            profile_response.raise_for_status()
            profile_payload = profile_response.json()

        expires_in = long_lived_payload.get("expires_in")
        token_expires_at = None
        if isinstance(expires_in, int):
            token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        granted_scopes = short_lived_payload.get("permissions") or self.settings.instagram_scopes

        return InstagramLinkResult(
            instagram_user_id=str(profile_payload["id"]),
            username=profile_payload.get("username"),
            access_token=long_lived_payload["access_token"],
            token_expires_at=token_expires_at,
            granted_scopes=[str(scope) for scope in granted_scopes],
        )
