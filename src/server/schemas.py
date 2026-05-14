"""Pydantic schemas — the JSON contract between FastAPI and the React UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from ..utils.booking_url import MAX_NIGHTS


JobKind = Literal["product", "hotel"]
AlertType = Literal["stock", "price", "price_drop"]
JobStatus = Literal["pending", "running", "idle", "alerted", "stopped", "error"]
EventKind = Literal["tick_start", "tick_result", "alert", "tick_done", "job_stop", "error"]


class JobCreate(BaseModel):
    url: str = Field(min_length=8)
    email: Optional[EmailStr] = None
    webhook_url: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    alert_type: AlertType
    threshold: Optional[float] = Field(default=None, ge=0)
    # Hotel night-range tracking. When BOTH are set, the runner scrapes
    # one URL per night in [date_start, date_end) and reports the cheapest.
    # Validated as a pair: either both or neither.
    date_start: Optional[date] = None
    date_end: Optional[date] = None

    @field_validator("url")
    @classmethod
    def _url_shape(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v

    @field_validator("webhook_url")
    @classmethod
    def _webhook_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("webhook_url must start with http:// or https://")
        return v

    @field_validator("telegram_chat_id")
    @classmethod
    def _telegram_chat_id_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        # Telegram chat IDs are integers (positive for users, negative for groups).
        try:
            int(v)
        except ValueError:
            raise ValueError("telegram_chat_id must be a numeric chat ID")
        return v

    @model_validator(mode="after")
    def _at_least_one_channel(self):
        if not self.email and not self.webhook_url and not self.telegram_chat_id:
            raise ValueError(
                "at least one delivery channel required "
                "(email, webhook_url, or telegram_chat_id)"
            )
        return self

    @model_validator(mode="after")
    def _validate_date_range(self):
        """Both or neither, end > start, capped at MAX_NIGHTS, no past start."""
        start, end = self.date_start, self.date_end
        if start is None and end is None:
            return self
        if start is None or end is None:
            raise ValueError("date_start and date_end must both be set or both omitted")
        if end <= start:
            raise ValueError("date_end must be after date_start")
        if (end - start).days > MAX_NIGHTS:
            raise ValueError(f"date range too long — max {MAX_NIGHTS} nights")
        today = datetime.now(timezone.utc).date()
        if start < today:
            raise ValueError("date_start must be today or later")
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    # Owner. Always present for jobs created post-auth; may be None on
    # legacy orphans an admin can still see until the claim sweep runs.
    user_id: Optional[str]
    kind: JobKind
    url: str
    email: Optional[EmailStr]
    webhook_url: Optional[str]
    telegram_chat_id: Optional[str]
    alert_type: AlertType
    threshold: Optional[float]
    platform: str
    status: JobStatus

    last_status: Optional[str]
    last_price: Optional[str]
    last_checked_at: Optional[datetime]
    alerted_at: Optional[datetime]

    # Night-range hotel watches expose their stay window + the cheapest
    # night found so far. All None for product / single-night watches.
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    cheapest_night_date: Optional[date] = None
    cheapest_night_price: Optional[float] = None

    active: bool
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    job_id: str
    job_kind: JobKind
    platform: str
    kind: EventKind
    message: str


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str


# ---- Auth ------------------------------------------------------------------


class MagicLinkRequest(BaseModel):
    """Body for POST /api/auth/request-magic-link."""

    email: EmailStr


class UserOut(BaseModel):
    """Public projection of a User row — what /api/auth/me returns."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: Optional[str]
    is_admin: bool
    telegram_chat_id: Optional[str]
    telegram_display_name: Optional[str]


class AuthMeResponse(BaseModel):
    """Bundles the User with the Telegram-bot status — one round-trip on mount."""

    user: UserOut
    telegram_bot_username: Optional[str] = None
    telegram_bot_configured: bool = False
