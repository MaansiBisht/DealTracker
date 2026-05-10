"""APScheduler wrapper.

One BackgroundScheduler runs in-process with a single-thread executor —
Selenium isn't safe to share across threads, so we serialise all ticks.

Cadence is env-overridable so you can dev-test in seconds and prod-run
in hours:
    TICK_INTERVAL_PRODUCT_SEC   default 30
    TICK_INTERVAL_HOTEL_SEC     default 60

For real Contabo deployment set these to 3600 and 10800.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from .db import SessionLocal
from .models import Job
from .runner import run_tick


log = logging.getLogger("dealtracker.scheduler")

PRODUCT_INTERVAL = int(os.getenv("TICK_INTERVAL_PRODUCT_SEC", "30"))
HOTEL_INTERVAL = int(os.getenv("TICK_INTERVAL_HOTEL_SEC", "60"))

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": ThreadPoolExecutor(max_workers=1)},
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
            timezone="UTC",
        )
    return _scheduler


def start() -> None:
    sch = get_scheduler()
    if not sch.running:
        sch.start()
        log.info("scheduler started · product=%ss hotel=%ss", PRODUCT_INTERVAL, HOTEL_INTERVAL)
    _reschedule_active_jobs()


def shutdown() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler stopped")


def schedule_job(job_id: str, kind: str) -> None:
    """Schedule (or replace) a recurring tick. First tick fires immediately."""
    interval = HOTEL_INTERVAL if kind == "hotel" else PRODUCT_INTERVAL
    sch = get_scheduler()
    sch.add_job(
        run_tick,
        trigger="interval",
        seconds=interval,
        args=[job_id],
        id=job_id,
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=2),
    )
    log.info("scheduled job %s every %ss", job_id, interval)


def unschedule_job(job_id: str) -> None:
    try:
        get_scheduler().remove_job(job_id)
        log.info("unscheduled job %s", job_id)
    except JobLookupError:
        pass


def _reschedule_active_jobs() -> None:
    with SessionLocal() as db:
        rows = list(db.scalars(select(Job).where(Job.active.is_(True))))
        for job in rows:
            schedule_job(job.id, job.kind)
        if rows:
            log.info("rescheduled %d active job(s) on startup", len(rows))
