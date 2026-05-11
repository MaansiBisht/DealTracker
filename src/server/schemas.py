"""Pydantic schemas — the JSON contract between FastAPI and the React UI."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


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
