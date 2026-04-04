import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from database import get_session
from schemas import AITriggerResponse, AIExpandRequest, AIExpandResponse
from services.ai_service import check_ollama_status, expand_reply
from services.queue_service import ai_queue, subscribe_sse, unsubscribe_sse, _SHUTDOWN_SENTINEL
from database import AsyncSessionLocal
from models import Email, AIStatus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/trigger", response_model=AITriggerResponse)
async def trigger_batch():
    """手动触发：将所有 pending 邮件加入 AI 处理队列"""
    count = await ai_queue.enqueue_pending()
    return AITriggerResponse(
        queued_count=count,
        message=f"已将 {count} 封待处理邮件加入队列" if count else "没有待处理邮件",
    )


@router.post("/trigger/{email_id}")
async def trigger_single(email_id: str):
    """对单封邮件触发 AI 分析（重置为 pending 并加入队列）"""
    async with AsyncSessionLocal() as session:
        em = await session.get(Email, email_id)
        if not em:
            raise HTTPException(status_code=404, detail="邮件不存在")
        em.ai_status = AIStatus.pending
        await session.commit()
    ai_queue.enqueue(email_id)
    return {"message": "已加入 AI 队列"}


@router.get("/stream")
async def ai_stream(request: Request):
    """SSE：实时推送 AI 处理进度事件"""
    q = subscribe_sse()

    async def event_generator():
        try:
            # 先推一次队列状态
            yield {
                "event": "status",
                "data": json.dumps({
                    "queue_size": ai_queue.queue_size,
                    "is_processing": ai_queue.is_processing,
                }),
            }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    if event is _SHUTDOWN_SENTINEL:
                        break  # 服务器关闭哨兵 → 立即退出 SSE 连接
                    yield {"event": "ai_update", "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    # 心跳，防止连接超时断开
                    yield {"event": "ping", "data": ""}
        finally:
            unsubscribe_sse(q)

    return EventSourceResponse(event_generator())


@router.get("/status")
async def ollama_status():
    """查询 Ollama 运行状态"""
    status = await check_ollama_status()
    status["queue_size"] = ai_queue.queue_size
    status["is_processing"] = ai_queue.is_processing
    return status


@router.post("/expand_reply", response_model=AIExpandResponse)
async def expand_reply_endpoint(
    body: AIExpandRequest,
    session: AsyncSession = Depends(get_session),
):
    """AI 扩写回复：将草稿扩写为完整专业邮件"""
    from models import UserPersona
    from sqlalchemy import select

    # 读 Persona
    persona_result = await session.execute(select(UserPersona).limit(1))
    persona = persona_result.scalar_one_or_none()
    role = persona.role or "" if persona else ""
    focus = persona.focus or "" if persona else ""
    tone = persona.tone or "专业、客观、直接" if persona else "专业、客观、直接"
    from services.ai_service import OLLAMA_MODEL
    model = (persona.ollama_model or OLLAMA_MODEL) if persona else OLLAMA_MODEL
    reply_system_prompt = (persona.reply_system_prompt or None) if persona else None

    # 读原邮件信息
    em = await session.get(Email, body.email_id)
    subject = em.subject if em else ""
    sender = em.sender if em else ""

    expanded = await expand_reply(
        draft=body.draft,
        subject=subject,
        original_sender=sender,
        role=role,
        focus=focus,
        tone=tone,
        model=model,
        reply_system_prompt=reply_system_prompt,
    )
    return AIExpandResponse(expanded=expanded)
