from __future__ import annotations

from app.core.security import create_access_token, decode_access_token


def test_access_token_round_trip() -> None:
    token = create_access_token("user-123")
    payload = decode_access_token(token)
    assert payload.sub == "user-123"
    assert payload.type == "access"
