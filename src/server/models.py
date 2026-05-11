"""ORM models for jobs and tick events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class User(Base):
    """Authenticated identity. Email-keyed; admins flagged on signin."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Persistent Telegram pairing — set once when /start <token> arrives.
    # Per-watch overrides still live on Job.telegram_chat_id.
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    telegram_display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginToken(Base):
    """One-time magic-link token. 15-minute TTL, single-use."""

    __tablename__ = "login_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # IPv6-safe address column for per-IP rate limiting.
    requested_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    url: Mapped[str] = mapped_column(Text)

    # Owner — nullable for legacy rows; populated for everything created
    # after auth lands. The admin claim sweep assigns orphans on first
    # admin signin.
    user_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # At least one delivery channel must be set. The schema layer enforces it.
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Per-watch Telegram routing — anyone's chat_id can be attached. Users
    # find their chat_id by sending any message to the bot, which replies
    # with it.
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    alert_type: Mapped[str] = mapped_column(String(16))
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    platform: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    last_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_price: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    alerted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    events: Mapped[list["Event"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Event.id.desc()",
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="events")


class TelegramPairing(Base):
    """One-time token issued when a user clicks Connect Telegram.

    Filled in by the long-poll worker when the user taps Start in
    Telegram (which sends "/start <token>" to the bot). The frontend
    polls /api/telegram/pairing/{token} until chat_id arrives, then
    drops it into the watch payload silently — the user never sees
    the chat_id or the token.
    """

    __tablename__ = "telegram_pairings"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Who requested this pairing. Nullable on legacy rows minted before
    # auth landed; populated for everything new.
    user_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chat_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    paired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


