import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import Response

from app.config import AUTH_SECRET, SESSION_COOKIE_NAME, SESSION_TTL_SECONDS


def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    rounds = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_str, salt_b64, digest_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_str)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_session_token(user_id: str) -> str:
    exp = now_epoch() + SESSION_TTL_SECONDS
    payload = f"{user_id}:{exp}".encode("utf-8")
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_b64url_encode(payload)}.{_b64url_encode(signature)}"


def parse_session_token(token: str) -> str | None:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64url_decode(payload_b64)
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None
        raw = payload.decode("utf-8")
        user_id, exp_str = raw.rsplit(":", 1)
        if now_epoch() > int(exp_str):
            return None
        return user_id
    except Exception:
        return None


def set_session_cookie(response: Response, user_id: str) -> None:
    token = create_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
