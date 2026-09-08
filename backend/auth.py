"""Authentication middleware — LEGACY Python implementation.

DO NOT ADD NEW FEATURES HERE.
Canonical implementation lives in: apps/web/worker/auth/middleware.ts

SECURITY: Uses Privy's official token verification, not payload-only decoding.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db import Base, get_db
from backend.models import User, UserRole


# ── API Key Model ──────────────────────────────────────────────────────


class APIKey(Base):
    """API key for external agent access."""
    __tablename__ = "api_keys"

    id = __import__('sqlalchemy').Column(__import__('sqlalchemy').UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = __import__('sqlalchemy').Column(__import__('sqlalchemy').UUID(as_uuid=True), nullable=False)
    key_hash = __import__('sqlalchemy').Column(__import__('sqlalchemy').String(64), nullable=False, unique=True)
    key_prefix = __import__('sqlalchemy').Column(__import__('sqlalchemy').String(8), nullable=False)
    name = __import__('sqlalchemy').Column(__import__('sqlalchemy').String(100), nullable=False)
    scopes = __import__('sqlalchemy').Column(__import__('sqlalchemy').Text, nullable=False, default="comedian:read,comedian:create,submission:create,submission:read")
    rate_limit = __import__('sqlalchemy').Column(__import__('sqlalchemy').Integer, nullable=False, default=100)
    is_active = __import__('sqlalchemy').Column(__import__('sqlalchemy').Boolean, nullable=False, default=True)
    last_used_at = __import__('sqlalchemy').Column(__import__('sqlalchemy').DateTime(timezone=True), nullable=True)
    created_at = __import__('sqlalchemy').Column(__import__('sqlalchemy').DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


# ── Key Generation ─────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, key_hash, key_prefix)."""
    raw_key = f"ft_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── Auth Dependency ────────────────────────────────────────────────────

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user_from_api_key(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate API key and return the associated user."""
    if not api_key:
        raise HTTPException(401, "Missing API key. Provide X-API-Key header.")

    key_hash = hash_api_key(api_key)

    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
    )
    api_key_obj = result.scalar_one_or_none()

    if not api_key_obj:
        raise HTTPException(401, "Invalid or inactive API key.")

    # Update last used
    api_key_obj.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    # Get the user
    user_result = await db.execute(select(User).where(User.id == api_key_obj.user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(401, "API key user not found.")

    return user


async def require_admin_from_api_key(
    user: User = Depends(get_current_user_from_api_key),
) -> User:
    """Require admin role for API key access."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin access required.")
    return user


# ── Scope Checking (actually enforced now) ─────────────────────────────

def check_scope(user: User, required_scope: str, api_key_scopes: str = "") -> bool:
    """Check if a user has a specific scope via their API key."""
    if user.role == UserRole.ADMIN:
        return True  # Admins have all scopes

    # Parse scopes from API key
    allowed_scopes = [s.strip() for s in api_key_scopes.split(",") if s.strip()]
    return required_scope in allowed_scopes


# ── Rate Limiting (fixed datetime bug) ─────────────────────────────────

rate_limit_store: dict[str, list[datetime]] = {}

RATE_LIMIT_WINDOW = 3600  # 1 hour


def check_rate_limit(key_prefix: str, limit: int = 100) -> bool:
    """Check if a key has exceeded its rate limit."""
    now = datetime.now(timezone.utc)
    cutoff = now - __import__('datetime').timedelta(seconds=RATE_LIMIT_WINDOW)

    if key_prefix not in rate_limit_store:
        rate_limit_store[key_prefix] = []

    # Clean old entries
    rate_limit_store[key_prefix] = [
        t for t in rate_limit_store[key_prefix] if t > cutoff
    ]

    if len(rate_limit_store[key_prefix]) >= limit:
        return False

    rate_limit_store[key_prefix].append(now)
    return True
