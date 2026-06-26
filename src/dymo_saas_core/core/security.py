import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from dymo_saas_core.core.config import settings
from dymo_saas_core.core.exceptions import UnauthorizedException

ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return ph.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password using Argon2id."""
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False

def create_access_token(payload: dict) -> str:
    """Create a short-lived JWT access token."""
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(payload: dict) -> str:
    """Create a long-lived JWT refresh token."""
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token has expired", "TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise UnauthorizedException("Invalid token", "INVALID_TOKEN")

def generate_secure_token() -> str:
    """Generate a high-entropy cryptographically secure random token."""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """SHA-256 hash of a token for secure database storage."""
    return hashlib.sha256(token.encode()).hexdigest()

def coerce_uuid(value: Any) -> uuid.UUID | Any:
    """Convert string UUID-like values to native UUID objects when possible."""
    if isinstance(value, uuid.UUID) or value is None:
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return value
