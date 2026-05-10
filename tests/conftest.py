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
    """Truncate jobs + events before every test for full isolation."""
    from sqlalchemy import delete
    from src.server.db import SessionLocal
    from src.server.models import Event, Job

    with SessionLocal() as db:
        db.execute(delete(Event))
        db.execute(delete(Job))
        db.commit()
    yield
