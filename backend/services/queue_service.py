"""
Async AI processing queue with single-worker execution and SSE broadcasts.
"""

import asyncio
import json
import logging
import subprocess

from sqlalchemy import select

from database import AsyncSessionLocal
from models import AIStatus, Email, UserPersona

logger = logging.getLogger(__name__)

_sse_subscribers: list[asyncio.Queue] = []
_SHUTDOWN_SENTINEL = object()


def subscribe_sse() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_subscribers.append(q)
    return q


def unsubscribe_sse(q: asyncio.Queue):
    try:
        _sse_subscribers.remove(q)
    except ValueError:
        pass


def _broadcast(event: dict):
    for q in _sse_subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def broadcast_shutdown():
    for q in _sse_subscribers:
        try:
            q.put_nowait(_SHUTDOWN_SENTINEL)
        except asyncio.QueueFull:
            pass


class AIQueue:
    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing = False
        self._ollama_proc: subprocess.Popen | None = None
        self._queued_ids: set[str] = set()
        self._inflight_ids: set[str] = set()

    def enqueue(self, email_id: str) -> bool:
        if email_id in self._queued_ids or email_id in self._inflight_ids:
            return False
        self._queued_ids.add(email_id)
        self._queue.put_nowait(email_id)
        return True

    async def enqueue_pending(self) -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Email.id).where(Email.ai_status.in_([AIStatus.pending, AIStatus.failed]))
            )
            ids = result.scalars().all()

        queued = 0
        for email_id in ids:
            if self.enqueue(email_id):
                queued += 1
        return queued

    async def _ensure_ollama_running(self) -> bool:
        from services.ai_service import check_ollama_status

        status = await check_ollama_status()
        if status["running"]:
            return True

        logger.info("Ollama 未运行，自动启动 ollama serve")
        try:
            self._ollama_proc = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.error("未找到 ollama 可执行文件，请确认已安装并在 PATH 中")
            return False

        for _ in range(30):
            await asyncio.sleep(1)
            status = await check_ollama_status()
            if status["running"]:
                logger.info("Ollama 已就绪")
                return True

        logger.error("Ollama 启动超时(30s)")
        return False

    async def _stop_ollama(self, model: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama",
                "stop",
                model,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            logger.info("Ollama 模型 '%s' 已卸载", model)
        except Exception as exc:
            logger.warning("ollama stop 失败: %s", exc)

        if self._ollama_proc:
            self._ollama_proc.terminate()
            self._ollama_proc = None
            logger.info("Ollama serve 进程已关闭")

    async def start_worker(self):
        logger.info("AI 队列 worker 已启动")
        while True:
            email_id = await self._queue.get()
            self._queued_ids.discard(email_id)
            self._inflight_ids.add(email_id)
            self._processing = True

            await self._ensure_ollama_running()
            try:
                await self._process(email_id)
            except Exception as exc:
                logger.error("处理邮件 %s 时发生意外错误: %s", email_id, exc)
            finally:
                self._processing = False
                self._inflight_ids.discard(email_id)
                self._queue.task_done()

            if self._queue.empty():
                from services.ai_service import OLLAMA_MODEL

                async with AsyncSessionLocal() as session:
                    persona_result = await session.execute(select(UserPersona).limit(1))
                    persona = persona_result.scalar_one_or_none()
                    model = (persona.ollama_model or OLLAMA_MODEL) if persona else OLLAMA_MODEL
                await self._stop_ollama(model)

    async def _process(self, email_id: str):
        from services.ai_service import OLLAMA_MODEL, analyze_email, get_default_tone

        async with AsyncSessionLocal() as session:
            em = await session.get(Email, email_id)
            if not em or em.ai_status not in (AIStatus.pending, AIStatus.failed):
                return

            persona_result = await session.execute(select(UserPersona).limit(1))
            persona = persona_result.scalar_one_or_none()
            language = (persona.language or "en-US") if persona else "en-US"
            role = persona.role or "" if persona else ""
            focus = persona.focus or "" if persona else ""
            tone = persona.tone or get_default_tone(language) if persona else get_default_tone(language)
            model = (persona.ollama_model or OLLAMA_MODEL) if persona else OLLAMA_MODEL
            analysis_system_prompt = (persona.analysis_system_prompt or None) if persona else None

            em.ai_status = AIStatus.processing
            await session.commit()

            subject = em.subject or ""
            sender = em.sender or ""
            body_text = em.body_text or ""

        _broadcast({"email_id": email_id, "ai_status": "processing"})

        result = await analyze_email(
            subject=subject,
            sender=sender,
            body_text=body_text,
            role=role,
            focus=focus,
            tone=tone,
            model=model,
            analysis_system_prompt=analysis_system_prompt,
            language=language,
        )

        async with AsyncSessionLocal() as session:
            em = await session.get(Email, email_id)
            if not em:
                return

            if result:
                em.ai_status = AIStatus.completed
                em.ai_importance = result.importance_score
                em.ai_is_important = result.is_important
                em.ai_summary = result.summary
                em.ai_ghost_reply = result.ghost_reply_suggestion
            else:
                em.ai_status = AIStatus.failed

            await session.commit()

            event = {
                "email_id": email_id,
                "ai_status": em.ai_status.value,
                "ai_importance": em.ai_importance,
                "ai_is_important": em.ai_is_important,
                "ai_summary": em.ai_summary,
                "ai_ghost_reply": em.ai_ghost_reply,
            }

        _broadcast(event)
        logger.info("邮件 %s AI 处理完成，重要度=%s", email_id, event["ai_importance"])

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_processing(self) -> bool:
        return self._processing


ai_queue = AIQueue()
