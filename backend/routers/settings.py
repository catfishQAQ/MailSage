from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import UserPersona
from schemas import PersonaOut, PersonaUpdate

router = APIRouter()


@router.get("/persona", response_model=PersonaOut)
async def get_persona(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(UserPersona).limit(1))
    persona = result.scalar_one_or_none()
    if not persona:
        persona = UserPersona()
        session.add(persona)
        await session.commit()
        await session.refresh(persona)
    return persona


@router.put("/persona", response_model=PersonaOut)
async def update_persona(data: PersonaUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(UserPersona).limit(1))
    persona = result.scalar_one_or_none()
    if not persona:
        persona = UserPersona()
        session.add(persona)

    if data.role is not None:
        persona.role = data.role
    if data.focus is not None:
        persona.focus = data.focus
    if data.tone is not None:
        persona.tone = data.tone
    if data.ollama_model is not None:
        persona.ollama_model = data.ollama_model
    hours_changed = False
    if data.sync_interval_hours is not None:
        persona.sync_interval_hours = data.sync_interval_hours
        hours_changed = True
    if data.analysis_system_prompt is not None:
        persona.analysis_system_prompt = data.analysis_system_prompt or None
    if data.reply_system_prompt is not None:
        persona.reply_system_prompt = data.reply_system_prompt or None

    await session.commit()
    await session.refresh(persona)

    if hours_changed:
        import asyncio
        from scheduler import reschedule_sync
        hours = persona.sync_interval_hours if persona.sync_interval_hours is not None else 2
        # 在线程池中执行，避免从事件循环线程直接调用 APScheduler 导致阻塞
        asyncio.get_running_loop().run_in_executor(None, reschedule_sync, hours)

    return persona
