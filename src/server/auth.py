"""Auth dependencies — signed-cookie sessions only.

Step 6 removed the legacy WEB_USER/WEB_PASS HTTP Basic codepath. Every
protected route now resolves the current User from the session cookie
set by /api/auth/verify after a magic-link click.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.requests import Request

from .db import get_session
from .models import User
from .sessions import current_user_id, logout_user


def current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> User:
    """Resolve the User row from the signed session, else 401.

    A stale session (cookie points at a deleted user) is cleared and
    treated as unauthenticated — the next request will see a fresh
    sign-in screen.
    """
    user_id = current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    user = db.get(User, user_id)
    if user is None:
        logout_user(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session no longer valid",
        )
    return user


def optional_current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> Optional[User]:
    """Like `current_user`, but returns None instead of raising on miss."""
    user_id = current_user_id(request)
    if not user_id:
        return None
    return db.get(User, user_id)
