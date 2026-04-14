import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./omnimail.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _infer_legacy_folder_role(mailbox: str | None) -> str:
    normalized = (mailbox or "INBOX").strip().lower()
    if normalized == "inbox":
        return "inbox"
    if normalized in {"spam", "junk", "垃圾邮件"}:
        return "junk"
    if normalized in {"trash", "deleted items", "已删除", "已删除邮件"}:
        return "trash"
    if normalized in {"archive", "归档"}:
        return "archive"
    if normalized in {"all mail", "[gmail]/all mail", "所有邮件"}:
        return "all"
    return "custom"


def _legacy_folder_priority(role: str) -> int:
    return {
        "inbox": 50,
        "custom": 40,
        "archive": 30,
        "junk": 20,
        "trash": 10,
    }.get(role, 0)


def _recompute_email_from_copies(email, copies):
    if not copies:
        return False

    primary_copy = sorted(
        copies,
        key=lambda copy: (
            -_legacy_folder_priority(copy.role),
            (copy.mailbox or "").lower(),
            copy.uid,
        ),
    )[0]
    email.folder = primary_copy.mailbox
    email.uid = primary_copy.uid
    email.is_read = any(copy.is_read for copy in copies)
    return True


async def _backfill_folder_metadata():
    from models import Account, AccountFolderState, Email, EmailFolderCopy

    async with AsyncSessionLocal() as session:
        accounts = (await session.execute(select(Account))).scalars().all()
        existing_states = {
            (state.account_id, state.mailbox)
            for state in (await session.execute(select(AccountFolderState))).scalars().all()
        }

        for account in accounts:
            key = (account.id, "INBOX")
            if key in existing_states:
                continue
            session.add(
                AccountFolderState(
                    id=str(uuid.uuid4()),
                    account_id=account.id,
                    mailbox="INBOX",
                    role="inbox",
                    include_in_sync=True,
                    last_uid=account.last_uid or 0,
                    last_seen_at=datetime.utcnow(),
                )
            )

        emails = (await session.execute(select(Email))).scalars().all()
        existing_copies = {
            (copy.account_id, copy.mailbox, copy.uid)
            for copy in (await session.execute(select(EmailFolderCopy))).scalars().all()
        }

        for email in emails:
            if not email.uid:
                continue
            mailbox = email.folder or "INBOX"
            key = (email.account_id, mailbox, email.uid)
            if key in existing_copies:
                continue
            session.add(
                EmailFolderCopy(
                    id=str(uuid.uuid4()),
                    email_id=email.id,
                    account_id=email.account_id,
                    mailbox=mailbox,
                    role=_infer_legacy_folder_role(mailbox),
                    uid=email.uid,
                    is_read=email.is_read,
                    last_synced_at=datetime.utcnow(),
                )
            )

        await session.commit()


async def _cleanup_all_mail_metadata():
    from models import AccountFolderState, Email, EmailFolderCopy

    async with AsyncSessionLocal() as session:
        all_states = (
            await session.execute(
                select(AccountFolderState).where(AccountFolderState.role == "all")
            )
        ).scalars().all()
        for state in all_states:
            await session.delete(state)

        all_copies = (
            await session.execute(
                select(EmailFolderCopy).where(EmailFolderCopy.role == "all")
            )
        ).scalars().all()
        affected_email_ids = {copy.email_id for copy in all_copies}
        for copy in all_copies:
            await session.delete(copy)

        if affected_email_ids:
            remaining_copies = (
                await session.execute(
                    select(EmailFolderCopy).where(EmailFolderCopy.email_id.in_(affected_email_ids))
                )
            ).scalars().all()
            copies_by_email_id: dict[str, list[EmailFolderCopy]] = {}
            for copy in remaining_copies:
                copies_by_email_id.setdefault(copy.email_id, []).append(copy)

            emails = (
                await session.execute(
                    select(Email).where(Email.id.in_(affected_email_ids))
                )
            ).scalars().all()
            for email in emails:
                remaining = copies_by_email_id.get(email.id, [])
                if not _recompute_email_from_copies(email, remaining):
                    await session.delete(email)

        await session.commit()


async def init_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)
        # 迁移：为已有 DB 添加 ollama_model 列（新建 DB 时由 create_all 处理，已有 DB 执行此语句）
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN ollama_model VARCHAR"))
        except Exception:
            pass  # 列已存在则忽略
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN sync_interval_hours INTEGER DEFAULT 2"))
        except Exception:
            pass  # 列已存在则忽略
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN analysis_system_prompt TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN reply_system_prompt TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN language VARCHAR DEFAULT 'en-US'"))
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE user_persona SET language = 'en-US' "
                "WHERE language IS NULL OR TRIM(language) = ''"
            )
        )
        try:
            await conn.execute(text("ALTER TABLE emails ADD COLUMN message_id VARCHAR"))
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE emails SET message_id = id "
                "WHERE message_id IS NULL OR TRIM(message_id) = ''"
            )
        )
        try:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN sent_last_uid INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN sent_folder VARCHAR"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN prompt_context TEXT"))
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE accounts SET sent_last_uid = 0 "
                "WHERE sent_last_uid IS NULL"
            )
        )
        try:
            await conn.execute(text("ALTER TABLE sent_replies ADD COLUMN source VARCHAR DEFAULT 'local'"))
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE sent_replies SET source = 'local' "
                "WHERE source IS NULL OR TRIM(source) = ''"
            )
        )
    await _backfill_folder_metadata()
    await _cleanup_all_mail_metadata()


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
