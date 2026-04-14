import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from database import AsyncSessionLocal, get_session
from models import AIStatus, Email
from schemas import AIExpandRequest, AIExpandResponse, AITriggerResponse
from services.ai_service import OLLAMA_MODEL, check_ollama_status, expand_reply, get_default_tone
from services.queue_service import (
    _SHUTDOWN_SENTINEL,
    ai_queue,
    subscribe_sse,
    unsubscribe_sse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/trigger", response_model=AITriggerResponse)
async def trigger_batch():
    count = await ai_queue.enqueue_pending()
    return AITriggerResponse(
        queued_count=count,
        message=f"Queued {count} emails for AI processing" if count else "No pending emails to process",
    )


@router.post("/trigger/{email_id}")
async def trigger_single(email_id: str):
    async with AsyncSessionLocal() as session:
        em = await session.get(Email, email_id)
        if not em:
            raise HTTPException(status_code=404, detail="Email not found")
        em.ai_status = AIStatus.pending
        await session.commit()
    ai_queue.enqueue(email_id)
    return {"message": "Added to AI queue"}


@router.get("/stream")
async def ai_stream(request: Request):
    q = subscribe_sse()

    async def event_generator():
        try:
            yield {
                "event": "status",
                "data": json.dumps(
                    {
                        "queue_size": ai_queue.queue_size,
                        "is_processing": ai_queue.is_processing,
                    }
                ),
            }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    if event is _SHUTDOWN_SENTINEL:
                        break
                    yield {"event": "ai_update", "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            unsubscribe_sse(q)

    return EventSourceResponse(event_generator())


@router.get("/status")
async def ollama_status():
    status = await check_ollama_status()
    status["queue_size"] = ai_queue.queue_size
    status["is_processing"] = ai_queue.is_processing
    return status


@router.post("/expand_reply", response_model=AIExpandResponse)
async def expand_reply_endpoint(
    body: AIExpandRequest,
    session: AsyncSession = Depends(get_session),
):
    from models import Account, UserPersona
    from sqlalchemy import select

    persona_result = await session.execute(select(UserPersona).limit(1))
    persona = persona_result.scalar_one_or_none()
    language = (persona.language or "en-US") if persona else "en-US"
    role = persona.role or "" if persona else ""
    focus = persona.focus or "" if persona else ""
    tone = persona.tone or get_default_tone(language) if persona else get_default_tone(language)
    model = (persona.ollama_model or OLLAMA_MODEL) if persona else OLLAMA_MODEL
    reply_system_prompt = (persona.reply_system_prompt or None) if persona else None

    em = await session.get(Email, body.email_id)
    subject = em.subject if em else ""
    sender = em.sender if em else ""
    account = await session.get(Account, em.account_id) if em else None
    account_prompt_context = account.prompt_context if account else None

    expanded = await expand_reply(
        draft=body.draft,
        subject=subject,
        original_sender=sender,
        role=role,
        focus=focus,
        tone=tone,
        model=model,
        reply_system_prompt=reply_system_prompt,
        account_prompt_context=account_prompt_context,
        language=language,
    )
    return AIExpandResponse(expanded=expanded)
