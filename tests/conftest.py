"""Shared fixtures.

Each test session uses an isolated in-memory SQLite — never the real
data/dealtracker.db — and never starts APScheduler so test runs are
fully sync, deterministic, and finish in milliseconds.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Force isolation BEFORE the app module imports happen. A per-session
# SQLite tempfile is more reliable than `:memory:` — the latter is
# per-connection, which loses tables across separate Sessions.
_TMP_DB = tempfile.NamedTemporaryFile(prefix="dealtracker-test-", suffix=".db", delete=False)
_TMP_DB.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")
os.environ.setdefault("WEB_USER", "")
os.environ.setdefault("WEB_PASS", "")
os.environ.setdefault("FALLBACK_EMAIL", "")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-do-not-use-in-prod-0123456789abcdef")
os.environ.setdefault("APP_BASE_URL", "http://testserver")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")


def pytest_sessionfinish(session, exitstatus):  # pragma: no cover
    try:
        os.unlink(_TMP_DB.name)
    except OSError:
        pass


@pytest.fixture(scope="session")
def app():
    """Build the FastAPI app once per session with the scheduler stubbed out."""
    import src.server.scheduler as scheduler_mod

    scheduler_mod.start = lambda: None
    scheduler_mod.shutdown = lambda: None
    scheduler_mod.schedule_job = lambda *a, **kw: None
    scheduler_mod.unschedule_job = lambda *a, **kw: None

    from src.server.db import init_db
    from src.server.main import app as fastapi_app

    init_db()
    return fastapi_app


@pytest.fixture()
def client(app):
    """TestClient — runs lifespan, talks to the in-memory DB."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _wipe_db(app):
    """Truncate every per-test table before each test for full isolation."""
    from sqlalchemy import delete
    from src.server.db import SessionLocal
    from src.server.models import Event, Job, LoginToken, TelegramPairing, User

    with SessionLocal() as db:
        db.execute(delete(Event))
        db.execute(delete(Job))
        db.execute(delete(TelegramPairing))
        db.execute(delete(LoginToken))
        db.execute(delete(User))
        db.commit()
    yield


@pytest.fixture()
def make_user():
    """Factory: create a User row directly (skipping the magic-link flow)."""
    from src.server.db import SessionLocal
    from src.server.models import User

    def _make(email: str, is_admin: bool = False) -> "User":
        with SessionLocal() as db:
            user = User(email=email.lower(), is_admin=is_admin)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    return _make


@pytest.fixture()
def auth_client(app, make_user):
    """TestClient factory pre-loaded with a signed session cookie for `user`.

    Mirrors Starlette `SessionMiddleware`'s wire format:
        cookie_value = TimestampSigner(SECRET).sign(b64(json(session_dict)))
    """
    from fastapi.testclient import TestClient
    from itsdangerous import TimestampSigner
    import base64
    import json as _json
    import os as _os

    def _client(user=None, *, email: str | None = None, is_admin: bool = False):
        if user is None:
            user = make_user(email or "user@example.com", is_admin=is_admin)
        secret = _os.environ["SESSION_SECRET"]
        payload = base64.b64encode(_json.dumps({"user_id": user.id}).encode())
        signed = TimestampSigner(secret).sign(payload).decode("utf-8")
        c = TestClient(app)
        c.cookies.set("dealtracker_session", signed)
        return c, user

    return _client
