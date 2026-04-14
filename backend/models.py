import enum
from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class AIStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=True)
    imap_host: Mapped[str] = mapped_column(String, nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    smtp_host: Mapped[str] = mapped_column(String, nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    prompt_context: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    # 加密后的密码（Fernet）
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    # 增量同步：记录上次同步的最大 UID
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    sent_last_uid: Mapped[int] = mapped_column(Integer, default=0)
    sent_folder: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    emails: Mapped[list["Email"]] = relationship(
        "Email",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sent_replies: Mapped[list["SentReply"]] = relationship(
        "SentReply",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    folder_states: Mapped[list["AccountFolderState"]] = relationship(
        "AccountFolderState",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    email_folder_copies: Mapped[list["EmailFolderCopy"]] = relationship(
        "EmailFolderCopy",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # internal UUID
    message_id: Mapped[str] = mapped_column(String, nullable=True)  # RFC Message-ID
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    uid: Mapped[int] = mapped_column(Integer, nullable=True)   # IMAP UID
    sender: Mapped[str] = mapped_column(String, nullable=False)
    sender_name: Mapped[str] = mapped_column(String, nullable=True)
    recipients: Mapped[str] = mapped_column(Text, nullable=True)  # JSON array
    subject: Mapped[str] = mapped_column(String, nullable=True, default="（无主题）")
    body_text: Mapped[str] = mapped_column(Text, nullable=True)   # 纯文本正文
    body_html: Mapped[str] = mapped_column(Text, nullable=True)   # 原始 HTML（已 sanitize）
    receive_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    folder: Mapped[str] = mapped_column(String, default="INBOX")

    # AI 字段
    ai_status: Mapped[AIStatus] = mapped_column(SAEnum(AIStatus), default=AIStatus.pending)
    ai_importance: Mapped[int] = mapped_column(Integer, nullable=True)   # 1-5
    ai_is_important: Mapped[bool] = mapped_column(Boolean, nullable=True)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=True)
    ai_action_items: Mapped[str] = mapped_column(Text, nullable=True)    # JSON array
    ai_ghost_reply: Mapped[str] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship("Account", back_populates="emails")
    sent_replies: Mapped[list["SentReply"]] = relationship(
        "SentReply",
        back_populates="source_email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    folder_copies: Mapped[list["EmailFolderCopy"]] = relationship(
        "EmailFolderCopy",
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AccountFolderState(Base):
    __tablename__ = "account_folder_states"
    __table_args__ = (
        UniqueConstraint("account_id", "mailbox", name="uq_account_folder_state"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mailbox: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="custom")
    include_in_sync: Mapped[bool] = mapped_column(Boolean, default=True)
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    account: Mapped["Account"] = relationship("Account", back_populates="folder_states")


class EmailFolderCopy(Base):
    __tablename__ = "email_folder_copies"
    __table_args__ = (
        UniqueConstraint("account_id", "mailbox", "uid", name="uq_email_folder_copy_uid"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mailbox: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="custom")
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    email: Mapped["Email"] = relationship("Email", back_populates="folder_copies")
    account: Mapped["Account"] = relationship("Account", back_populates="email_folder_copies")


class SentReply(Base):
    __tablename__ = "sent_replies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_email_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    in_reply_to: Mapped[str] = mapped_column(String, nullable=True)
    references: Mapped[str] = mapped_column(Text, nullable=True)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=True, default="(No subject)")
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="local")

    source_email: Mapped["Email"] = relationship("Email", back_populates="sent_replies")
    account: Mapped["Account"] = relationship("Account", back_populates="sent_replies")


class UserPersona(Base):
    __tablename__ = "user_persona"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    role: Mapped[str] = mapped_column(String, nullable=True, default="")
    focus: Mapped[str] = mapped_column(Text, nullable=True, default="")
    tone: Mapped[str] = mapped_column(String, nullable=True, default="专业、客观、直接")
    ollama_model: Mapped[str] = mapped_column(String, nullable=True, default=None)
    sync_interval_hours: Mapped[int] = mapped_column(Integer, nullable=True, default=2)
    language: Mapped[str] = mapped_column(String, nullable=True, default="en-US")
    analysis_system_prompt: Mapped[str] = mapped_column(Text, nullable=True, default=None)
    reply_system_prompt: Mapped[str] = mapped_column(Text, nullable=True, default=None)
