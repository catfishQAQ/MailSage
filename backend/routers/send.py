import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Email, SentReply
from schemas import SendResponse, SentReplyOut
from services.smtp_service import send_email

router = APIRouter()


class SendRequest(BaseModel):
    account_id: str
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None


@router.post("/send", response_model=SendResponse)
async def send(req: SendRequest, session: AsyncSession = Depends(get_session)):
    source_email = None
    if req.reply_to_message_id:
        result = await session.execute(
            select(Email).where(
                Email.account_id == req.account_id,
                or_(
                    Email.message_id == req.reply_to_message_id,
                    Email.id == req.reply_to_message_id,
                ),
            ).limit(1)
        )
        source_email = result.scalar_one_or_none()

    if source_email is None:
        raise HTTPException(status_code=404, detail="未找到对应的原始邮件，无法记录回信")

    try:
        send_result = await send_email(
            account_id=req.account_id,
            to=req.to,
            subject=req.subject,
            body=req.body,
            reply_to_message_id=req.reply_to_message_id,
        )
        sent_reply = SentReply(
            id=str(uuid.uuid4()),
            source_email_id=source_email.id,
            account_id=req.account_id,
            message_id=send_result.message_id,
            in_reply_to=send_result.in_reply_to,
            references=send_result.references,
            recipient=send_result.recipient,
            subject=send_result.subject,
            body_text=send_result.body_text,
            sent_at=send_result.sent_at,
        )
        session.add(sent_reply)
        await session.commit()
        await session.refresh(sent_reply)
        return SendResponse(ok=True, sent_reply=SentReplyOut.model_validate(sent_reply))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
