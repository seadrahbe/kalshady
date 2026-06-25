from __future__ import annotations

import secrets

from cryptography.fernet import Fernet

from app.config import get_settings

_fernet: Fernet | None = None


def _f() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_settings().fernet_key.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a secret (bank token, PAN) for storage at rest."""
    return _f().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _f().decrypt(token.encode()).decode()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
