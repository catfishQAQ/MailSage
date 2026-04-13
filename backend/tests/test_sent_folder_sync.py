import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base
from models import Account, Email, SentReply
from services import imap_service


class FakeListImap:
    def __init__(self, responses):
        self.responses = responses

    def list(self):
        return "OK", self.responses


class SentFolderSyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            poolclass=StaticPool,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _seed_account_and_email(self):
        async with self.session_factory() as session:
            account = Account(
                id="account-1",
                email="sender@example.com",
                display_name="Sender",
                imap_host="imap.example.com",
                imap_port=993,
                imap_use_ssl=True,
                smtp_host="smtp.example.com",
                smtp_port=465,
                smtp_use_ssl=True,
                encrypted_password="ciphertext",
                last_uid=0,
                sent_last_uid=0,
                sent_folder=None,
                is_active=True,
            )
            email = Email(
                id="email-1",
                message_id="<source@example.com>",
                account_id=account.id,
                uid=101,
                sender="recipient@example.com",
                sender_name="Recipient",
                recipients="[]",
                subject="Important test",
                body_text="Incoming body",
                body_html=None,
                receive_time=datetime(2026, 4, 13, 15, 0, 0),
                is_read=True,
                has_attachments=False,
                folder="INBOX",
            )
            session.add(account)
            session.add(email)
            await session.commit()

    def test_find_sent_mailbox_prefers_sent_flag(self):
        mailbox = imap_service._find_sent_mailbox(
            FakeListImap(
                [
                    b'(\\HasNoChildren) "/" "INBOX"',
                    b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"',
                ]
            )
        )

        self.assertEqual(mailbox, "[Gmail]/Sent Mail")

    async def test_merge_sent_replies_imports_history_and_updates_sync_state(self):
        await self._seed_account_and_email()

        with patch.object(imap_service, "AsyncSessionLocal", self.session_factory):
            inserted = await imap_service._merge_sent_replies(
                account_id="account-1",
                parsed_sent_messages=[
                    {
                        "id": "reply-1",
                        "message_id": "<sent-1@example.com>",
                        "in_reply_to": "<source@example.com>",
                        "references": "<source@example.com>",
                        "candidate_source_message_ids": ["<source@example.com>"],
                        "recipient": "recipient@example.com",
                        "subject": "Re: Important test",
                        "body_text": "Imported from Sent",
                        "sent_at": datetime(2026, 4, 13, 15, 5, 0),
                    }
                ],
                sent_last_uid=88,
                sent_folder="[Gmail]/Sent Mail",
            )

        self.assertEqual(inserted, 1)

        async with self.session_factory() as session:
            account = await session.get(Account, "account-1")
            replies = (await session.execute(select(SentReply))).scalars().all()

        self.assertEqual(account.sent_last_uid, 88)
        self.assertEqual(account.sent_folder, "[Gmail]/Sent Mail")
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].source_email_id, "email-1")
        self.assertEqual(replies[0].body_text, "Imported from Sent")

    async def test_merge_sent_replies_skips_duplicates_and_unmatched_messages(self):
        await self._seed_account_and_email()

        async with self.session_factory() as session:
            session.add(
                SentReply(
                    id="existing",
                    source_email_id="email-1",
                    account_id="account-1",
                    message_id="<sent-1@example.com>",
                    in_reply_to="<source@example.com>",
                    references="<source@example.com>",
                    recipient="recipient@example.com",
                    subject="Re: Important test",
                    body_text="Existing",
                    sent_at=datetime(2026, 4, 13, 15, 4, 0),
                )
            )
            await session.commit()

        with patch.object(imap_service, "AsyncSessionLocal", self.session_factory):
            inserted = await imap_service._merge_sent_replies(
                account_id="account-1",
                parsed_sent_messages=[
                    {
                        "id": "reply-duplicate",
                        "message_id": "<sent-1@example.com>",
                        "in_reply_to": "<source@example.com>",
                        "references": "<source@example.com>",
                        "candidate_source_message_ids": ["<source@example.com>"],
                        "recipient": "recipient@example.com",
                        "subject": "Re: Important test",
                        "body_text": "Duplicate",
                        "sent_at": datetime(2026, 4, 13, 15, 5, 0),
                    },
                    {
                        "id": "reply-unmatched",
                        "message_id": "<sent-2@example.com>",
                        "in_reply_to": "<missing@example.com>",
                        "references": "<missing@example.com>",
                        "candidate_source_message_ids": ["<missing@example.com>"],
                        "recipient": "recipient@example.com",
                        "subject": "Re: Important test",
                        "body_text": "Unmatched",
                        "sent_at": datetime(2026, 4, 13, 15, 6, 0),
                    },
                ],
                sent_last_uid=90,
                sent_folder="Sent",
            )

        self.assertEqual(inserted, 0)

        async with self.session_factory() as session:
            replies = (await session.execute(select(SentReply))).scalars().all()

        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].message_id, "<sent-1@example.com>")


if __name__ == "__main__":
    unittest.main()
