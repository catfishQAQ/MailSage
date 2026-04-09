import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Email, AIStatus
from schemas import EmailDetail, EmailListItem, EmailListResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=EmailListResponse)
async def list_emails(
    account_id: str | None = Query(None, description="筛选账号 ID"),
    ai_status: AIStatus | None = Query(None, description="按 AI 状态筛选"),
    is_important: bool | None = Query(None, description="只显示重要邮件"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Email)
    if account_id:
        stmt = stmt.where(Email.account_id == account_id)
    if ai_status:
        stmt = stmt.where(Email.ai_status == ai_status)
    if is_important is not None:
        stmt = stmt.where(Email.ai_is_important == is_important)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # 分页，按时间倒序
    stmt = stmt.order_by(desc(Email.receive_time))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()

    return EmailListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{email_id}", response_model=EmailDetail)
async def get_email(email_id: str, session: AsyncSession = Depends(get_session)):
    em = await session.get(Email, email_id)
    if not em:
        raise HTTPException(status_code=404, detail="邮件不存在")

    logger.info("[get_email] id=%s is_read=%s uid=%s", email_id, em.is_read, em.uid)

    # 标记已读（本地 DB + IMAP 服务器）
    if not em.is_read:
        account_id, uid = em.account_id, em.uid
        em.is_read = True
        await session.commit()
        await session.refresh(em)
        # fire-and-forget：后台写回 IMAP \Seen 标志
        from services.imap_service import mark_as_read
        asyncio.create_task(mark_as_read(account_id, uid or 0))

    return em


@router.get("/pending/count")
async def pending_count(
    account_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """获取待 AI 处理的邮件数量（pending + failed 均计入）"""
    stmt = select(func.count()).where(
        Email.ai_status.in_([AIStatus.pending, AIStatus.failed])
    )
    if account_id:
        stmt = stmt.where(Email.account_id == account_id)
    count = (await session.execute(stmt)).scalar_one()
    return {"pending": count}
