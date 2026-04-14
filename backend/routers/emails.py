import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import AIStatus, Email, EmailFolderCopy, SentReply
from schemas import (
    BulkMarkReadRequest,
    BulkMarkReadResponse,
    EmailDetail,
    EmailListItem,
    EmailListResponse,
    SentReplyListResponse,
    SentReplyOut,
)
from services.imap_service import mailbox_display_name, mark_as_read, mark_copies_as_read

logger = logging.getLogger(__name__)
router = APIRouter()

_SUPPORTED_EMAIL_VIEWS = {"all", "important", "unread"}


def _normalize_view(view: str | None) -> str:
    normalized = (view or "all").strip().lower()
    if normalized not in _SUPPORTED_EMAIL_VIEWS:
        raise HTTPException(status_code=400, detail=f"Unsupported email view: {normalized}")
    return normalized


def _sent_reply_to_out(sent_reply: SentReply) -> SentReplyOut:
    return SentReplyOut.model_validate(sent_reply)


@router.get("/sent", response_model=SentReplyListResponse)
async def list_sent_replies(
    account_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(SentReply)
    if account_id:
        stmt = stmt.where(SentReply.account_id == account_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(desc(SentReply.sent_at)).offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()

    return SentReplyListResponse(
        items=[_sent_reply_to_out(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sent/{sent_reply_id}", response_model=SentReplyOut)
async def get_sent_reply(sent_reply_id: str, session: AsyncSession = Depends(get_session)):
    sent_reply = await session.get(SentReply, sent_reply_id)
    if not sent_reply:
        raise HTTPException(status_code=404, detail="Sent reply not found")
    return _sent_reply_to_out(sent_reply)


@router.post("/mark-read-all", response_model=BulkMarkReadResponse)
async def mark_all_unread_as_read(
    payload: BulkMarkReadRequest,
    session: AsyncSession = Depends(get_session),
):
    emails = (
        await session.execute(
            select(Email)
            .where(Email.account_id == payload.account_id, Email.is_read == False)  # noqa: E712
            .order_by(Email.receive_time.desc())
        )
    ).scalars().all()

    if not emails:
        return BulkMarkReadResponse(updated_count=0)

    email_ids = [email.id for email in emails]
    copies = (
        await session.execute(
            select(EmailFolderCopy).where(EmailFolderCopy.email_id.in_(email_ids))
        )
    ).scalars().all()

    copies_to_mark = [(copy.mailbox, copy.uid) for copy in copies if copy.uid]
    for email in emails:
        email.is_read = True
        if email.ai_status == AIStatus.pending:
            email.ai_status = AIStatus.completed
    for copy in copies:
        copy.is_read = True

    await session.commit()
    await mark_copies_as_read(payload.account_id, copies_to_mark)
    return BulkMarkReadResponse(updated_count=len(emails))


@router.get("/", response_model=EmailListResponse)
async def list_emails(
    account_id: str | None = Query(None, description="Filter by account ID"),
    ai_status: AIStatus | None = Query(None, description="Filter by AI status"),
    is_important: bool | None = Query(None, description="Legacy important filter"),
    view: str | None = Query(None, description="Account-scoped email view"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    normalized_view = _normalize_view(view)

    stmt = select(Email)
    if account_id:
        stmt = stmt.where(Email.account_id == account_id)
    if ai_status:
        stmt = stmt.where(Email.ai_status == ai_status)
    if normalized_view == "important" or is_important is True:
        stmt = stmt.where(Email.ai_is_important == True)  # noqa: E712
    elif normalized_view == "unread":
        stmt = stmt.where(Email.is_read == False)  # noqa: E712
    elif is_important is False:
        stmt = stmt.where(Email.ai_is_important == False)  # noqa: E712

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(desc(Email.receive_time)).offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()

    return EmailListResponse(
        items=[
            EmailListItem(
                id=item.id,
                message_id=item.message_id,
                account_id=item.account_id,
                sender=item.sender,
                sender_name=item.sender_name,
                subject=item.subject,
                receive_time=item.receive_time,
                is_read=item.is_read,
                has_attachments=item.has_attachments,
                folder=mailbox_display_name(item.folder),
                ai_status=item.ai_status,
                ai_importance=item.ai_importance,
                ai_is_important=item.ai_is_important,
                ai_summary=item.ai_summary,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/pending/count")
async def pending_count(
    account_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(func.count()).where(
        Email.ai_status.in_([AIStatus.pending, AIStatus.failed])
    )
    if account_id:
        stmt = stmt.where(Email.account_id == account_id)
    count = (await session.execute(stmt)).scalar_one()
    return {"pending": count}


@router.get("/{email_id}", response_model=EmailDetail)
async def get_email(email_id: str, session: AsyncSession = Depends(get_session)):
    em = await session.get(Email, email_id)
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")

    logger.info("[get_email] id=%s is_read=%s uid=%s folder=%s", email_id, em.is_read, em.uid, em.folder)

    if not em.is_read:
        account_id, uid, folder = em.account_id, em.uid, em.folder
        em.is_read = True
        await session.commit()
        await session.refresh(em)
        asyncio.create_task(mark_as_read(account_id, uid or 0, folder))

    folder_copy_result = await session.execute(
        select(EmailFolderCopy)
        .where(EmailFolderCopy.email_id == em.id)
        .order_by(EmailFolderCopy.mailbox.asc(), EmailFolderCopy.uid.asc())
    )
    folder_copies = folder_copy_result.scalars().all()
    folders: list[str] = []
    for copy in folder_copies:
        display_name = mailbox_display_name(copy.mailbox)
        if display_name not in folders:
            folders.append(display_name)

    sent_replies_result = await session.execute(
        select(SentReply)
        .where(SentReply.source_email_id == em.id)
        .order_by(SentReply.sent_at.asc())
    )
    sent_replies = sent_replies_result.scalars().all()

    return EmailDetail(
        id=em.id,
        message_id=em.message_id,
        account_id=em.account_id,
        sender=em.sender,
        sender_name=em.sender_name,
        recipients=em.recipients,
        subject=em.subject,
        body_text=em.body_text,
        body_html=em.body_html,
        receive_time=em.receive_time,
        is_read=em.is_read,
        has_attachments=em.has_attachments,
        folder=mailbox_display_name(em.folder),
        folders=folders or [mailbox_display_name(em.folder)],
        ai_status=em.ai_status,
        ai_importance=em.ai_importance,
        ai_is_important=em.ai_is_important,
        ai_summary=em.ai_summary,
        ai_ghost_reply=em.ai_ghost_reply,
        sent_replies=[_sent_reply_to_out(sent_reply) for sent_reply in sent_replies],
    )
