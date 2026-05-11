"""Session helpers — thin wrappers over Starlette's signed-cookie session.

The cookie is the only thing the server reads; we never trust anything
in it except the user_id. The user row is fetched fresh per request so
admin/email/telegram changes show up without re-signing.
"""

from __future__ import annotations

import os
from typing import Optional

from starlette.requests import Request


SESSION_KEY = "user_id"


def session_secret() -> str:
    """Return SESSION_SECRET or raise — fails fast at app boot if unset."""
    secret = os.getenv("SESSION_SECRET", "").strip()
    if not secret:
        raise RuntimeError(
            "SESSION_SECRET must be set (32+ random bytes). Generate with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    return secret


def session_cookie_secure() -> bool:
    """HTTPS-only cookie flag. On unless APP_BASE_URL is http:// (dev)."""
    base = os.getenv("APP_BASE_URL", "").strip().lower()
    return not base.startswith("http://")


def login_user(request: Request, user_id: str) -> None:
    """Place the user_id into the signed session cookie."""
    request.session[SESSION_KEY] = user_id


def logout_user(request: Request) -> None:
    """Wipe every session key — clears the cookie on the next response."""
    request.session.clear()


def current_user_id(request: Request) -> Optional[str]:
    """Return the user_id from the signed session, or None if absent."""
    value = request.session.get(SESSION_KEY)
    if isinstance(value, str) and value:
        return value
    return None
