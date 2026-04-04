"""
AI 处理队列（asyncio 单 worker 串行）。
防爆显存：同一时刻只有一封邮件在被 LLM 处理。
SSE 广播：处理完每封邮件后通过 asyncio.Queue 通知 SSE 端点推送事件。
"""
import asyncio
import json
import logging
import subprocess

from sqlalchemy import select

from database import AsyncSessionLocal
from models import Email, AIStatus, UserPersona

logger = logging.getLogger(__name__)

# SSE 广播订阅列表（每个 SSE 连接一个 Queue）
_sse_subscribers: list[asyncio.Queue] = []

# 关闭哨兵：广播此对象通知所有 SSE 连接退出
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
    """向所有 SSE 订阅者广播关闭哨兵，让连接立即退出"""
    for q in _sse_subscribers:
        try:
            q.put_nowait(_SHUTDOWN_SENTINEL)
        except asyncio.QueueFull:
            pass


class AIQueue:
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
        self._ollama_proc: subprocess.Popen | None = None  # 我们自动启动的进程

    def enqueue(self, email_id: str):
        self._queue.put_nowait(email_id)

    async def enqueue_pending(self) -> int:
        """将所有 pending 和 failed 状态邮件加入队列，返回加入数量"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Email.id).where(
                    Email.ai_status.in_([AIStatus.pending, AIStatus.failed])
                )
            )
            ids = result.scalars().all()

        for eid in ids:
            self.enqueue(eid)
        return len(ids)

    async def _ensure_ollama_running(self) -> bool:
        """若 Ollama 未运行，自动启动并等待就绪（最多 30s）。"""
        from services.ai_service import check_ollama_status
        status = await check_ollama_status()
        if status["running"]:
            return True
        logger.info("Ollama 未运行，自动启动 ollama serve …")
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
        logger.error("Ollama 启动超时（30s）")
        return False

    async def _stop_ollama(self, model: str):
        """卸载模型（释放显存），若是我们启动的进程则终止。"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "stop", model,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            logger.info("Ollama 模型 '%s' 已卸载，显存已释放", model)
        except Exception as e:
            logger.warning("ollama stop 失败: %s", e)
        if self._ollama_proc:
            self._ollama_proc.terminate()
            self._ollama_proc = None
            logger.info("Ollama serve 进程已关闭")

    async def start_worker(self):
        """单 worker 协程，串行处理队列中的邮件"""
        logger.info("AI 队列 worker 已启动")
        while True:
            email_id = await self._queue.get()
            self._processing = True
            # 确保 Ollama 运行（若未运行则自动启动）
            await self._ensure_ollama_running()
            try:
                await self._process(email_id)
            except Exception as e:
                logger.error("处理邮件 %s 时发生意外错误: %s", email_id, e)
            finally:
                self._processing = False
                self._queue.task_done()

            # 队列已空 → 本次 batch 结束，卸载模型释放显存
            if self._queue.empty():
                from services.ai_service import OLLAMA_MODEL
                async with AsyncSessionLocal() as session:
                    persona_result = await session.execute(select(UserPersona).limit(1))
                    persona = persona_result.scalar_one_or_none()
                    model = (persona.ollama_model or OLLAMA_MODEL) if persona else OLLAMA_MODEL
                await self._stop_ollama(model)

    async def _process(self, email_id: str):
        from services.ai_service import analyze_email, OLLAMA_MODEL

        async with AsyncSessionLocal() as session:
            em = await session.get(Email, email_id)
            if not em or em.ai_status not in (AIStatus.pending, AIStatus.failed):
                return

            # 读取 Persona
            persona_result = await session.execute(select(UserPersona).limit(1))
            persona = persona_result.scalar_one_or_none()
            role = persona.role or "" if persona else ""
            focus = persona.focus or "" if persona else ""
            tone = persona.tone or "专业、客观、直接" if persona else "专业、客观、直接"
            model = (persona.ollama_model or OLLAMA_MODEL) if persona else OLLAMA_MODEL
            analysis_system_prompt = (persona.analysis_system_prompt or None) if persona else None
            logger.info("AI 分析使用模型: '%s'（DB 值: %s）",
                        model, persona.ollama_model if persona else "无 persona")

            # 标记 processing
            em.ai_status = AIStatus.processing
            await session.commit()

        _broadcast({"email_id": email_id, "ai_status": "processing"})

        # 调用 LLM（在 session 关闭后执行，避免长时间持有连接）
        result = await analyze_email(
            subject=em.subject or "",
            sender=em.sender or "",
            body_text=em.body_text or "",
            role=role,
            focus=focus,
            tone=tone,
            model=model,
            analysis_system_prompt=analysis_system_prompt,
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
                em.ai_action_items = json.dumps(result.action_items, ensure_ascii=False)
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
        logger.info("邮件 %s AI 处理完成，重要性=%s", email_id, em.ai_importance)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_processing(self) -> bool:
        return self._processing


# 全局单例
ai_queue = AIQueue()
