"""APScheduler 定时任务：定期同步所有邮箱 + 触发 AI 处理，频率可在设置中配置"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _scheduled_job():
    from services.imap_service import sync_all_accounts
    from services.queue_service import ai_queue

    logger.info("定时任务：开始同步邮件")
    await sync_all_accounts()

    count = await ai_queue.enqueue_pending()
    logger.info("定时任务：已将 %d 封邮件加入 AI 队列", count)


async def start_scheduler():
    """启动调度器，同步频率从 DB 读取（默认 2 小时）"""
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
        logger.info("定时任务调度器已启动（每 %d 小时）", hours)
    else:
        logger.info("定时任务调度器已启动（手动模式，不自动同步）")
    _scheduler.start()


def reschedule_sync(hours: int):
    """用新的间隔时间重新调度同步任务；hours=0 表示手动模式，移除定时任务"""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return
    try:
        if hours == 0:
            try:
                _scheduler.remove_job("email_sync")
            except Exception:
                pass
            logger.info("定时同步已关闭（手动模式）")
        else:
            try:
                _scheduler.reschedule_job("email_sync", trigger=IntervalTrigger(hours=hours))
            except Exception:
                # 任务不存在（之前是手动模式），重新添加
                _scheduler.add_job(
                    _scheduled_job,
                    trigger=IntervalTrigger(hours=hours),
                    id="email_sync",
                    replace_existing=True,
                )
            logger.info("定时同步已更新为每 %d 小时", hours)
    except Exception as exc:
        logger.warning("reschedule_sync 失败（已忽略）: %s", exc)


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
