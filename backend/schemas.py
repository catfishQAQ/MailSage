from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from models import AIStatus


# ── Account ──────────────────────────────────────────────
class AccountCreate(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None
    imap_host: str
    imap_port: int = 993
    imap_use_ssl: bool = True
    smtp_host: str
    smtp_port: int = 465
    smtp_use_ssl: bool = True
    password: str  # 明文，后端加密后存储


class AccountUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class AccountOut(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    is_active: bool
    last_uid: int

    model_config = {"from_attributes": True}


# ── Email ─────────────────────────────────────────────────
class EmailListItem(BaseModel):
    id: str
    message_id: Optional[str] = None
    account_id: str
    sender: str
    sender_name: Optional[str]
    subject: str
    receive_time: datetime
    is_read: bool
    has_attachments: bool
    ai_status: AIStatus
    ai_importance: Optional[int]
    ai_is_important: Optional[bool]
    ai_summary: Optional[str]

    model_config = {"from_attributes": True}


class EmailDetail(BaseModel):
    id: str
    message_id: Optional[str] = None
    account_id: str
    sender: str
    sender_name: Optional[str]
    recipients: Optional[str]
    subject: str
    body_text: Optional[str]
    body_html: Optional[str]
    receive_time: datetime
    is_read: bool
    has_attachments: bool
    folder: str
    ai_status: AIStatus
    ai_importance: Optional[int]
    ai_is_important: Optional[bool]
    ai_summary: Optional[str]
    ai_ghost_reply: Optional[str]
    sent_replies: list["SentReplyOut"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EmailListResponse(BaseModel):
    items: list[EmailListItem]
    total: int
    page: int
    page_size: int


# ── AI ────────────────────────────────────────────────────
class AITriggerResponse(BaseModel):
    queued_count: int
    message: str


class AIExpandRequest(BaseModel):
    email_id: str
    draft: str  # ghost reply 原文 或 用户手写草稿


class AIExpandResponse(BaseModel):
    expanded: str


class SentReplyOut(BaseModel):
    id: str
    message_id: str
    recipient: str
    subject: Optional[str]
    body_text: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class SendResponse(BaseModel):
    ok: bool
    sent_reply: SentReplyOut


# ── Persona ───────────────────────────────────────────────
class PersonaUpdate(BaseModel):
    role: Optional[str] = None
    focus: Optional[str] = None
    tone: Optional[str] = None
    ollama_model: Optional[str] = None
    sync_interval_hours: Optional[int] = None
    language: Optional[str] = None
    analysis_system_prompt: Optional[str] = None
    reply_system_prompt: Optional[str] = None


class PersonaOut(BaseModel):
    id: int
    role: Optional[str]
    focus: Optional[str]
    tone: Optional[str]
    ollama_model: Optional[str] = None
    sync_interval_hours: Optional[int] = None
    language: Optional[str] = None
    analysis_system_prompt: Optional[str] = None
    reply_system_prompt: Optional[str] = None

    model_config = {"from_attributes": True}


# ── SSE Event ─────────────────────────────────────────────
class AIStatusEvent(BaseModel):
    email_id: str
    ai_status: AIStatus
    ai_importance: Optional[int] = None
    ai_is_important: Optional[bool] = None
    ai_summary: Optional[str] = None
    ai_ghost_reply: Optional[str] = None


EmailDetail.model_rebuild()
