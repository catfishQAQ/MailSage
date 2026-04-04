from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.smtp_service import send_email

router = APIRouter()


class SendRequest(BaseModel):
    account_id: str
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None


@router.post("/send")
async def send(req: SendRequest):
    try:
        await send_email(
            account_id=req.account_id,
            to=req.to,
            subject=req.subject,
            body=req.body,
            reply_to_message_id=req.reply_to_message_id,
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
