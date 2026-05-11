"""Magic-link login — token issuance, consumption, rate limits, claims.

Flow:
    1. UI submits an email. `issue_token` writes a LoginToken row and
       returns the token string. The route then emails the user a
       link that embeds the token.
    2. User clicks the link → server hits `consume_token`, which:
        - rejects expired or already-used tokens,
        - marks the token used,
        - upserts the User by email,
        - recomputes is_admin from ADMIN_EMAIL,
        - on admin login, claims any orphan Job/TelegramPairing rows.

Rate limits prevent abuse: per-email and per-IP windows over the last
hour, both backed by the same LoginToken rows (no extra table).
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .models import Job, LoginToken, TelegramPairing, User


log = logging.getLogger("dealtracker.auth.magic_link")

TOKEN_BYTES = 32  # → 43-char urlsafe string, fits VARCHAR(64).
TOKEN_TTL_MINUTES = 15
RATE_LIMIT_PER_EMAIL_PER_HOUR = 5
RATE_LIMIT_PER_IP_PER_HOUR = 20


class RateLimitedError(RuntimeError):
    """Raised when an email or IP exceeds the per-hour magic-link quota."""

    def __init__(self, retry_after_seconds: int, scope: str) -> None:
        super().__init__(f"rate limit exceeded ({scope}); retry in {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds
        self.scope = scope


class TokenInvalidError(RuntimeError):
    """Raised when a token is unknown, expired, or already used."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _admin_email() -> Optional[str]:
    value = os.getenv("ADMIN_EMAIL", "").strip().lower()
    return value or None


# ---------- rate limit checks -------------------------------------------------


def _count_recent_for_email(db: Session, email: str, since: datetime) -> int:
    stmt = select(func.count()).select_from(LoginToken).where(
        LoginToken.email == email,
        LoginToken.created_at >= since,
    )
    return int(db.execute(stmt).scalar() or 0)


def _count_recent_for_ip(db: Session, ip: str, since: datetime) -> int:
    stmt = select(func.count()).select_from(LoginToken).where(
        LoginToken.requested_ip == ip,
        LoginToken.created_at >= since,
    )
    return int(db.execute(stmt).scalar() or 0)


def _retry_after_for_email(db: Session, email: str, since: datetime) -> int:
    """How long until the email's oldest in-window request rolls off."""
    stmt = (
        select(LoginToken.created_at)
        .where(LoginToken.email == email, LoginToken.created_at >= since)
        .order_by(LoginToken.created_at.asc())
        .limit(1)
    )
    oldest = db.execute(stmt).scalar_one_or_none()
    if oldest is None:
        return 60
    # SQLite returns naive datetimes; assume they're already UTC because we
    # always wrote them as such via `_now()`.
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    rolls_off = oldest + timedelta(hours=1)
    return max(1, int((rolls_off - _now()).total_seconds()))


# ---------- issuance ----------------------------------------------------------


def issue_token(db: Session, email: str, ip: Optional[str]) -> IssuedToken:
    """Mint a one-time login token. Raises RateLimitedError on quota breach."""
    normalised = _normalise_email(email)
    window_start = _now() - timedelta(hours=1)

    email_hits = _count_recent_for_email(db, normalised, window_start)
    if email_hits >= RATE_LIMIT_PER_EMAIL_PER_HOUR:
        raise RateLimitedError(
            retry_after_seconds=_retry_after_for_email(db, normalised, window_start),
            scope="email",
        )

    if ip:
        ip_hits = _count_recent_for_ip(db, ip, window_start)
        if ip_hits >= RATE_LIMIT_PER_IP_PER_HOUR:
            raise RateLimitedError(retry_after_seconds=60 * 15, scope="ip")

    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires_at = _now() + timedelta(minutes=TOKEN_TTL_MINUTES)
    db.add(
        LoginToken(
            token=token,
            email=normalised,
            created_at=_now(),
            expires_at=expires_at,
            used_at=None,
            requested_ip=ip,
        )
    )
    db.commit()
    return IssuedToken(token=token, expires_at=expires_at)


# ---------- consumption -------------------------------------------------------


def consume_token(db: Session, token: str) -> User:
    """Validate and burn a token; return the (created-or-found) User."""
    row = db.get(LoginToken, token)
    if row is None:
        raise TokenInvalidError("unknown_token")

    # Normalise expires_at timezone — SQLite-naive comparison would silently
    # be wrong without it.
    expires_at = row.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if row.used_at is not None:
        raise TokenInvalidError("token_already_used")
    if expires_at is None or expires_at < _now():
        raise TokenInvalidError("token_expired")

    row.used_at = _now()
    db.flush()

    user = _upsert_user(db, row.email)
    _apply_admin_status(user)
    if user.is_admin:
        _claim_orphans(db, user.id)
    user.last_login_at = _now()
    db.commit()
    db.refresh(user)
    return user


def _upsert_user(db: Session, email: str) -> User:
    stmt = select(User).where(User.email == email)
    user = db.execute(stmt).scalar_one_or_none()
    if user is not None:
        return user
    user = User(email=email)
    db.add(user)
    db.flush()
    return user


def _apply_admin_status(user: User) -> None:
    """Recompute is_admin from the current ADMIN_EMAIL env on every login."""
    admin_email = _admin_email()
    desired = admin_email is not None and user.email == admin_email
    if user.is_admin != desired:
        user.is_admin = desired


def _claim_orphans(db: Session, admin_id: str) -> int:
    """Assign every user_id IS NULL row in jobs + telegram_pairings to admin."""
    jobs_claimed = db.execute(
        update(Job).where(Job.user_id.is_(None)).values(user_id=admin_id)
    ).rowcount or 0
    pairings_claimed = db.execute(
        update(TelegramPairing).where(TelegramPairing.user_id.is_(None)).values(user_id=admin_id)
    ).rowcount or 0
    total = jobs_claimed + pairings_claimed
    if total:
        log.info("admin %s claimed %d orphan rows (%d jobs, %d pairings)",
                 admin_id, total, jobs_claimed, pairings_claimed)
    return total


# ---------- maintenance -------------------------------------------------------


def prune_expired_tokens(db: Session, older_than_hours: int = 24) -> int:
    """Drop tokens older than the rate-limit window so the table stays small."""
    cutoff = _now() - timedelta(hours=older_than_hours)
    result = db.execute(delete(LoginToken).where(LoginToken.created_at < cutoff))
    db.commit()
    return result.rowcount or 0
