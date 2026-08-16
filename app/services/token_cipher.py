from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import get_settings


class TokenCipher:
    def __init__(self) -> None:
        self._fernet = Fernet(get_settings().app_encryption_key.encode("utf-8"))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
