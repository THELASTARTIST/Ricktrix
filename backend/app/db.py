"""Supabase clients and request authentication.

Two clients on purpose:
* the anon key, for reads the browser is also allowed to make;
* the service-role key, for writes that must bypass row-level security (the
  seeder, and submissions from anonymous users).

The service key never leaves the server -- it must not appear in any response,
and the frontend only ever sees the anon key.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Header, HTTPException, status

from app import config

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_anon_client():
    if not config.using_supabase():
        return None
    from supabase import create_client

    return create_client(config.supabase_url(), config.supabase_anon_key())


@lru_cache(maxsize=1)
def get_service_client():
    """Server-side client. Returns None if the service key is not configured."""
    url, key = config.supabase_url(), config.supabase_service_key()
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


async def get_optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    """Resolve the caller from a Supabase JWT, or None if there isn't one.

    Endpoints that accept anonymous callers (route submissions) use this.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None

    client = get_anon_client()
    if client is None:
        return None
    try:
        response = client.auth.get_user(token)
    except Exception as exc:  # noqa: BLE001
        log.warning("token validation failed: %s", exc)
        return None

    user = getattr(response, "user", None)
    return dict(user) if user else None


async def require_user(authorization: str | None = Header(default=None)) -> dict:
    """Require a valid Supabase session, or 401."""
    user = await get_optional_user(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sign in to use this endpoint",
        )
    return user


async def require_admin(authorization: str | None = Header(default=None)) -> dict:
    """Require a valid session whose email is in ADMIN_EMAILS.

    Guards the moderation queue.
    """
    user = await require_user(authorization)
    email = (user.get("email") or "").lower()
    if email not in config.admin_emails():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not an administrator",
        )
    return user
