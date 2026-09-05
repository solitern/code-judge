"""Password hashing and signed cookie helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (InvalidHashError, VerificationError, ValueError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64(raw)}.{_b64(sig)}"


def verify_signed_payload(token: str, secret: str) -> dict[str, Any] | None:
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _unb64(raw_b64)
        sig = _unb64(sig_b64)
        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def create_session_token(username: str, secret: str, max_age_seconds: int) -> str:
    payload = {"sub": username, "exp": int(time.time()) + max_age_seconds, "iat": int(time.time())}
    return sign_payload(payload, secret)


def new_csrf_token() -> str:
    return secrets.token_hex(32)
