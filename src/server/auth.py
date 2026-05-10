"""HTTP Basic auth dependency.

If WEB_USER and WEB_PASS are set, every protected route requires them.
If either is unset, auth is disabled (intended for local dev).
"""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


_basic = HTTPBasic(auto_error=False)


def _expected() -> tuple[str, str] | None:
    user = os.getenv("WEB_USER")
    pwd = os.getenv("WEB_PASS")
    if user and pwd:
        return (user, pwd)
    return None


def require_user(creds: HTTPBasicCredentials | None = Depends(_basic)) -> str:
    """Return the authenticated username, or 'anonymous' if auth is disabled."""
    expected = _expected()
    if expected is None:
        return "anonymous"

    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth required",
            headers={"WWW-Authenticate": 'Basic realm="dealtracker"'},
        )

    user_ok = secrets.compare_digest(creds.username.encode(), expected[0].encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), expected[1].encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad credentials",
            headers={"WWW-Authenticate": 'Basic realm="dealtracker"'},
        )
    return creds.username
