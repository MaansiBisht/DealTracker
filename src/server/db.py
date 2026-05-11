"""SQLite engine and Session dependency for FastAPI."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "dealtracker.db"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH.as_posix()}",
)


def _ensure_data_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        path = Path(url.replace("sqlite:///", "", 1))
        path.parent.mkdir(parents=True, exist_ok=True)


_ensure_data_dir(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables, then run idempotent migrations for existing DBs."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_jobs_for_v2_channels()
    _migrate_add_user_columns()


def _migrate_jobs_for_v2_channels() -> None:
    """Add webhook_url + relax email NOT NULL on the jobs table.

    Idempotent: safe to run on every boot. Fresh DBs are produced by
    create_all already matching the v2 schema; only legacy DBs with
    NOT NULL email + no webhook_url need actual work.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "jobs" not in insp.get_table_names():
        return

    cols = {c["name"]: c for c in insp.get_columns("jobs")}

    # Step 1: add new nullable columns — SQLite supports ALTER ADD COLUMN.
    if "webhook_url" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN webhook_url TEXT"))
    if "telegram_chat_id" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN telegram_chat_id VARCHAR(32)"))

    # `telegram_pairings` is created automatically by Base.metadata.create_all.
    # Old `notify_telegram` column may exist on legacy DBs (SQLite can't drop
    # columns easily); the ORM no longer references it, so it's a harmless
    # orphan and we leave it in place.

    # Step 2: relax email NOT NULL on legacy tables. SQLite can't change
    # an existing column's nullability, so recreate the table once.
    insp_again = inspect(engine)
    email_col = {c["name"]: c for c in insp_again.get_columns("jobs")}.get("email", {})
    if email_col.get("nullable") is False:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE jobs RENAME TO jobs_legacy_v1"))
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            conn.execute(text(
                """
                INSERT INTO jobs (
                    id, kind, url, email, webhook_url, alert_type, threshold,
                    platform, status,
                    last_status, last_price, last_checked_at, alerted_at,
                    active, created_at
                )
                SELECT
                    id, kind, url, email, NULL, alert_type, threshold,
                    platform, status,
                    last_status, last_price, last_checked_at, alerted_at,
                    active, created_at
                FROM jobs_legacy_v1
                """
            ))
            conn.execute(text("DROP TABLE jobs_legacy_v1"))


def _migrate_add_user_columns() -> None:
    """Add `user_id` to legacy jobs / telegram_pairings tables.

    Idempotent: existence check via SQLAlchemy inspector before ALTER.
    Fresh DBs already have the column via `create_all`; only legacy
    DBs minted before auth landed need work. Legacy rows stay NULL
    until the admin claim sweep runs on first admin signin.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for table in ("jobs", "telegram_pairings"):
        if table not in existing_tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "user_id" in cols:
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR(32)"))
