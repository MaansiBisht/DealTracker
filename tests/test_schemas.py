"""Pydantic schema validation — the JSON contract."""

import pytest
from pydantic import ValidationError

from src.server.schemas import JobCreate


def test_jobcreate_accepts_minimal_product():
    payload = JobCreate(
        url="https://www.amazon.in/dp/B08BPQ9CZ1",
        email="me@example.com",
        alert_type="stock",
    )
    assert payload.threshold is None


def test_jobcreate_strips_whitespace_in_url():
    payload = JobCreate(
        url="  https://www.amazon.in/dp/B08BPQ9CZ1  ",
        email="me@example.com",
        alert_type="stock",
    )
    assert payload.url == "https://www.amazon.in/dp/B08BPQ9CZ1"


def test_jobcreate_rejects_non_http_url():
    with pytest.raises(ValidationError) as ei:
        JobCreate(url="ftp://x", email="me@example.com", alert_type="stock")
    assert "http" in str(ei.value).lower()


def test_jobcreate_rejects_invalid_email():
    with pytest.raises(ValidationError):
        JobCreate(
            url="https://www.amazon.in/dp/foo",
            email="not-an-email",
            alert_type="stock",
        )


def test_jobcreate_rejects_unknown_alert_type():
    with pytest.raises(ValidationError):
        JobCreate(
            url="https://www.amazon.in/dp/foo",
            email="me@example.com",
            alert_type="banana",
        )


def test_jobcreate_rejects_negative_threshold():
    with pytest.raises(ValidationError):
        JobCreate(
            url="https://www.amazon.in/dp/foo",
            email="me@example.com",
            alert_type="price",
            threshold=-1,
        )
