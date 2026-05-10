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
    assert payload.webhook_url is None


def test_jobcreate_accepts_webhook_only():
    payload = JobCreate(
        url="https://www.amazon.in/dp/foo",
        webhook_url="https://hooks.example.com/abc",
        alert_type="stock",
    )
    assert payload.email is None
    assert payload.webhook_url == "https://hooks.example.com/abc"


def test_jobcreate_accepts_both_channels():
    payload = JobCreate(
        url="https://www.amazon.in/dp/foo",
        email="me@example.com",
        webhook_url="https://hooks.example.com/abc",
        alert_type="stock",
    )
    assert payload.email == "me@example.com"
    assert payload.webhook_url == "https://hooks.example.com/abc"


def test_jobcreate_rejects_no_channels():
    with pytest.raises(ValidationError) as ei:
        JobCreate(
            url="https://www.amazon.in/dp/foo",
            alert_type="stock",
        )
    assert "at least one delivery channel" in str(ei.value)


def test_jobcreate_accepts_telegram_chat_id_only():
    payload = JobCreate(
        url="https://www.amazon.in/dp/foo",
        telegram_chat_id="987654321",
        alert_type="stock",
    )
    assert payload.email is None
    assert payload.webhook_url is None
    assert payload.telegram_chat_id == "987654321"


def test_jobcreate_rejects_non_numeric_chat_id():
    with pytest.raises(ValidationError):
        JobCreate(
            url="https://www.amazon.in/dp/foo",
            telegram_chat_id="@johndoe",
            alert_type="stock",
        )


def test_jobcreate_treats_blank_chat_id_as_none():
    """Blank chat_id with email present is fine; it's just not the channel."""
    payload = JobCreate(
        url="https://www.amazon.in/dp/foo",
        email="me@example.com",
        telegram_chat_id="   ",
        alert_type="stock",
    )
    assert payload.telegram_chat_id is None


def test_jobcreate_rejects_invalid_webhook():
    with pytest.raises(ValidationError):
        JobCreate(
            url="https://www.amazon.in/dp/foo",
            webhook_url="ftp://nope",
            alert_type="stock",
        )


def test_jobcreate_treats_blank_webhook_as_none():
    """Whitespace-only webhook = no webhook configured."""
    payload = JobCreate(
        url="https://www.amazon.in/dp/foo",
        email="me@example.com",
        webhook_url="   ",
        alert_type="stock",
    )
    assert payload.webhook_url is None


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
