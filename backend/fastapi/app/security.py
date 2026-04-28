from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

from passlib.hash import bcrypt as passlib_bcrypt

from .config import settings


PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260000
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._\-]+$")


def hash_password(password: str) -> str:
    salt_bytes = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    if encoded.startswith("$2y$") or encoded.startswith("$2b$") or encoded.startswith("$2a$"):
        return _verify_bcrypt_password(password, encoded)
    try:
        prefix, iter_raw, salt_hex, digest_hex = encoded.split("$", 3)
        if prefix != PBKDF2_PREFIX:
            return False
        iterations = int(iter_raw)
        salt_bytes = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _verify_bcrypt_password(password: str, encoded: str) -> bool:
    try:
        normalized = encoded
        if encoded.startswith("$2y$"):
            normalized = f"$2b${encoded[4:]}"
        return passlib_bcrypt.verify(password, normalized)
    except Exception:
        return False


def hash_token(raw_token: str) -> str:
    payload = (settings.secret_key + raw_token).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(settings.token_bytes)


def normalize_username(value: str) -> str:
    return value.strip()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_role(value: str | None) -> str:
    if str(value or "").lower() == "admin":
        return "admin"
    return "user"


def validate_username(value: str) -> str | None:
    clean = normalize_username(value)
    if len(clean) < 2:
        return "用户名至少需要2个字符"
    if len(clean) > 50:
        return "用户名不能超过50个字符"
    if not USERNAME_PATTERN.match(clean):
        return "用户名只允许字母、数字、点、下划线和中划线"
    return None


def validate_email(value: str) -> str | None:
    clean = normalize_email(value)
    if not clean:
        return None
    if len(clean) > 120:
        return "邮箱不能超过120个字符"
    if not EMAIL_PATTERN.match(clean):
        return "邮箱格式不正确"
    return None


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "密码至少需要8个字符"
    if len(password) > 128:
        return "密码不能超过128个字符"

    checks = [
        any(ch.islower() for ch in password),
        any(ch.isupper() for ch in password),
        any(ch.isdigit() for ch in password),
    ]
    if sum(checks) < 2:
        return "密码需至少包含大小写字母/数字中的两种"
    return None
