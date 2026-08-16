from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@dataclass(slots=True)
class GoogleOAuthIdentity:
    google_sub: str
    email: str
    name: str
    picture_url: str | None
    access_token: str
    refresh_token: str | None
    id_token: str | None
    access_token_expires_at: datetime | None
    scope: str | None


class GoogleAuthService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_authorization_url(self, redirect_uri: str, state: str) -> str:
        if not self.settings.google_client_id:
            raise ValueError("CLIENT_ID is not configured.")

        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> GoogleOAuthIdentity:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise ValueError("CLIENT_ID or CLIENT_SECRET is not configured.")

        timeout = self.settings.request_timeout_seconds
        with httpx.Client(timeout=timeout) as client:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            token_payload = token_response.json()

            access_token = token_payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("Google did not return an access token.")

            userinfo_response = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            userinfo_payload = userinfo_response.json()

        google_sub = userinfo_payload.get("sub")
        email = userinfo_payload.get("email")
        name = userinfo_payload.get("name")
        if not isinstance(google_sub, str) or not isinstance(email, str) or not isinstance(name, str):
            raise ValueError("Google user profile response was incomplete.")

        expires_at = None
        expires_in = token_payload.get("expires_in")
        if isinstance(expires_in, int):
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        refresh_token = token_payload.get("refresh_token")
        id_token = token_payload.get("id_token")
        scope = token_payload.get("scope")

        return GoogleOAuthIdentity(
            google_sub=google_sub,
            email=email,
            name=name,
            picture_url=userinfo_payload.get("picture") if isinstance(userinfo_payload.get("picture"), str) else None,
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) else None,
            id_token=id_token if isinstance(id_token, str) else None,
            access_token_expires_at=expires_at,
            scope=scope if isinstance(scope, str) else None,
        )
