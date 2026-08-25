"""Password hashing helpers."""

import base64
import hashlib
import hmac
import secrets

PASSWORD_HASH_NAME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """Hash a plain password with PBKDF2-SHA256."""

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    )
    encoded_digest = base64.b64encode(digest).decode("ascii")
    return f"{PASSWORD_HASH_NAME}${PASSWORD_HASH_ITERATIONS}${salt}${encoded_digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plain password against a stored PBKDF2 hash."""

    try:
        hash_name, iterations, salt, encoded_digest = password_hash.split("$", maxsplit=3)
    except ValueError:
        return False

    if hash_name != PASSWORD_HASH_NAME:
        return False

    expected_digest = base64.b64decode(encoded_digest.encode("ascii"))
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    )
    return hmac.compare_digest(actual_digest, expected_digest)


__all__ = ["hash_password", "verify_password"]
