"""Pydantic schemas — the JSON contract between FastAPI and the React UI."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


JobKind = Literal["product", "hotel"]
AlertType = Literal["stock", "price", "price_drop"]
JobStatus = Literal["pending", "running", "idle", "alerted", "stopped", "error"]
EventKind = Literal["tick_start", "tick_result", "alert", "tick_done", "job_stop", "error"]


class JobCreate(BaseModel):
    url: str = Field(min_length=8)
    email: EmailStr
    alert_type: AlertType
    threshold: Optional[float] = Field(default=None, ge=0)

    @field_validator("url")
    @classmethod
    def _url_shape(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: JobKind
    url: str
    email: EmailStr
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
    kind: EventKind
    message: str


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str
