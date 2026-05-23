"""APScheduler: nightly summary generation (UTC midnight by default)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.dependencies import (
    _build_news_fetcher,
    _build_summarizer,
    _build_telegram_sender,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.summary_service import SummaryMaintenanceService

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

SUMMARY_JOB_ID = "summary_generation_midnight"


def _nightly_summary_job() -> None:
    db = SessionLocal()
    try:
        maintenance = SummaryMaintenanceService(
            db,
            summarizer=_build_summarizer(),
            fetcher=_build_news_fetcher(db),
            telegram_sender=_build_telegram_sender(),
        )
        stats = maintenance.run_bulk_for_all_users()
        logger.info("Nightly summary job finished: %s", stats)
    except Exception:
        logger.exception("Nightly summary job failed")
        db.rollback()
    finally:
        db.close()


def setup_scheduler() -> None:
    global _scheduler
    if not settings.enable_summary_nightly_scheduler:
        logger.info("Nightly summary scheduler disabled (ENABLE_SUMMARY_NIGHTLY_SCHEDULER=false)")
        return
    if _scheduler is not None:
        return
    sched = AsyncIOScheduler()
    tz = settings.summary_schedule_timezone.strip() or "UTC"
    sched.add_job(
        _nightly_summary_job,
        CronTrigger(hour=0, minute=0, second=0, timezone=tz),
        id=SUMMARY_JOB_ID,
        replace_existing=True,
    )
    sched.start()
    logger.info(
        "Nightly summary scheduler started (cron 00:00, timezone=%s)",
        tz,
    )
    _scheduler = sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Nightly summary scheduler stopped")
    _scheduler = None
