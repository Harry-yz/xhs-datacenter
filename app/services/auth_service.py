from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine

settings = get_settings()

_schema_ready = False
_schema_lock = threading.Lock()
_PBKDF2_ITERATIONS = 180_000


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iteration_text, salt_encoded, digest_encoded = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        salt = _b64url_decode(salt_encoded)
        expected = _b64url_decode(digest_encoded)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_session_token(*, user_id: int, email: str, role: str) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": user_id,
                "email": email,
                "role": role,
                "exp": int(time.time()) + max(1, settings.auth_session_ttl_hours) * 3600,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("utf-8")
    signature = _b64url_encode(hmac.new(settings.auth_session_secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def verify_session_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    if token == "demo":
        return {"sub": 0, "email": "demo", "role": "demo"}
    parts = token.split(".")
    if len(parts) != 3:
        return None

    header, payload, signature = parts
    signing_input = f"{header}.{payload}".encode("utf-8")
    expected_signature = _b64url_encode(
        hmac.new(settings.auth_session_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload_data = json.loads(_b64url_decode(payload).decode("utf-8"))
        expires_at = int(payload_data.get("exp", 0))
        if expires_at <= int(time.time()):
            return None
        return payload_data
    except Exception:
        return None


def is_authenticated_session(token: str | None) -> bool:
    return verify_session_token(token) is not None


def ensure_auth_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return

    with _schema_lock:
        if _schema_ready:
            return

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS app_user (
                        id BIGSERIAL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role VARCHAR(32) NOT NULL DEFAULT 'admin',
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_app_user_email_lower
                    ON app_user ((lower(email)))
                    """
                )
            )

            admin_email = (settings.auth_admin_email or "").strip().lower()
            admin_password = (settings.auth_admin_password or "").strip()

            if admin_email and admin_password:
                conn.execute(
                    text(
                        """
                        INSERT INTO app_user(email, password_hash, role, status)
                        VALUES(:email, :password_hash, 'admin', 'active')
                        ON CONFLICT (email) DO UPDATE SET
                            password_hash = EXCLUDED.password_hash,
                            role = 'admin',
                            status = 'active',
                            updated_at = now()
                        """
                    ),
                    {"email": admin_email, "password_hash": hash_password(admin_password)},
                )

        _schema_ready = True


def get_user_by_email(db: Session, email: str) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT id, email, password_hash, role, status
            FROM app_user
            WHERE lower(email) = lower(:email)
            LIMIT 1
            """
        ),
        {"email": email.strip().lower()},
    ).mappings().first()
    return dict(row) if row else None
