"""APScheduler periodic sync jobs."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def run_sync_cycle(trigger: str = "scheduled") -> None:
    """Run one full sync cycle and enqueue pending emails for AI."""
    from services.imap_service import sync_all_accounts
    from services.queue_service import ai_queue

    logger.info("Sync cycle started (trigger=%s)", trigger)
    await sync_all_accounts()
    queued = await ai_queue.enqueue_pending()
    logger.info("Sync cycle completed (trigger=%s), queued=%d", trigger, queued)


async def _scheduled_job() -> None:
    await run_sync_cycle(trigger="scheduled")


async def start_scheduler() -> None:
    """Start scheduler with sync interval loaded from user settings."""
    from database import AsyncSessionLocal
    from models import UserPersona
    from sqlalchemy import select

    hours = 2
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserPersona).limit(1))
        persona = result.scalar_one_or_none()
        if persona and persona.sync_interval_hours is not None:
            hours = persona.sync_interval_hours

    global _scheduler
    _scheduler = AsyncIOScheduler()
    if hours > 0:
        _scheduler.add_job(
            _scheduled_job,
            trigger=IntervalTrigger(hours=hours),
            id="email_sync",
            replace_existing=True,
        )
        logger.info("Scheduled sync enabled (every %d hours)", hours)
    else:
        logger.info("Scheduled sync disabled (manual mode)")
    _scheduler.start()


def reschedule_sync(hours: int) -> None:
    """Reschedule sync interval; hours=0 means manual mode."""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return
    try:
        if hours == 0:
            try:
                _scheduler.remove_job("email_sync")
            except Exception:
                pass
            logger.info("Scheduled sync disabled (manual mode)")
            return

        try:
            _scheduler.reschedule_job("email_sync", trigger=IntervalTrigger(hours=hours))
        except Exception:
            _scheduler.add_job(
                _scheduled_job,
                trigger=IntervalTrigger(hours=hours),
                id="email_sync",
                replace_existing=True,
            )
        logger.info("Scheduled sync interval updated to %d hours", hours)
    except Exception as exc:
        logger.warning("reschedule_sync failed (ignored): %s", exc)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)

