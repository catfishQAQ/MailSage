import sys
import unittest
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from database import Base
from models import Account, AccountFolderState, Email, EmailFolderCopy
from services import imap_service


class FakeMailboxImap:
    def __init__(self, message: EmailMessage):
        self.message = message

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, *args):
        command = command.lower()
        if command == "search":
            criteria = " ".join(str(arg) for arg in args if arg is not None)
            if "ALL" in criteria and "SINCE" not in criteria:
                return "OK", [b"1 2 3"]
            if "SINCE" in criteria:
                return "OK", [b"2 3"]
            if "UID" in criteria:
                return "OK", [b"3"]
        if command == "fetch":
            if args[1] == "(UID FLAGS)":
                return "OK", [b"1 (UID 3 FLAGS (\\Seen))"]
            if args[1] == "(BODY.PEEK[])":
                return "OK", [(b"1 (UID 3 RFC822 {42}", self.message.as_bytes()), b")"]
        raise AssertionError(f"Unexpected uid call: {command} {args}")


class MultiFolderSyncTests(unittest.IsolatedAsyncioTestCase):
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

    async def _seed_account(self):
        async with self.session_factory() as session:
            session.add(
                Account(
                    id="account-1",
                    email="owner@example.com",
                    display_name="Owner",
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
            )
            await session.commit()

    def test_classify_mailbox_prefers_flags_then_name_fallback(self):
        self.assertEqual(imap_service._classify_mailbox({"\\junk"}, "INBOX")[0], "junk")
        self.assertEqual(imap_service._classify_mailbox(set(), "垃圾邮件")[0], "junk")
        self.assertEqual(imap_service._classify_mailbox(set(), "Projects")[0], "custom")
        self.assertFalse(imap_service._classify_mailbox(set(), "Drafts")[1])
        role, include = imap_service._classify_mailbox({"\\all"}, "[Gmail]/All Mail")
        self.assertEqual(role, "all")
        self.assertFalse(include)

    def test_search_initial_uids_uses_recent_window_and_tracks_max_uid(self):
        msg = EmailMessage()
        fake_imap = FakeMailboxImap(msg)

        recent_uids, max_uid = imap_service._search_initial_uids(fake_imap)

        self.assertEqual(recent_uids, ["2", "3"])
        self.assertEqual(max_uid, 3)

    def test_all_mail_is_not_an_incoming_role(self):
        msg = EmailMessage()
        msg["Message-ID"] = "<sent@example.com>"
        msg["From"] = "owner@example.com"
        msg["To"] = "friend@example.com"
        msg["Subject"] = "Re: Thread"
        msg["Date"] = "Sun, 13 Apr 2026 12:00:00 +0000"
        msg.set_content("Hello")
        fake_imap = FakeMailboxImap(msg)

        parsed, max_uid = imap_service._fetch_mailbox_messages(
            fake_imap,
            mailbox="[Gmail]/All Mail",
            mailbox_role="all",
            last_uid=0,
        )

        self.assertEqual(len(parsed), 1)
        self.assertEqual(max_uid, 3)

    async def test_merge_incoming_mailboxes_dedupes_and_prefers_inbox_as_primary_folder(self):
        await self._seed_account()
        parsed_emails = [
            {
                "id": "email-junk",
                "message_id": "<source@example.com>",
                "normalized_message_id": "<source@example.com>",
                "uid": 10,
                "mailbox": "垃圾邮件",
                "mailbox_role": "junk",
                "sender": "sender@example.com",
                "sender_name": "Sender",
                "recipients": "[]",
                "subject": "Important test",
                "body_text": "Same body",
                "body_html": None,
                "receive_time": datetime(2026, 4, 13, 12, 0, 0),
                "has_attachments": False,
                "is_read": False,
                "fingerprint": "fp-1",
            },
            {
                "id": "email-inbox",
                "message_id": "<source@example.com>",
                "normalized_message_id": "<source@example.com>",
                "uid": 20,
                "mailbox": "INBOX",
                "mailbox_role": "inbox",
                "sender": "sender@example.com",
                "sender_name": "Sender",
                "recipients": "[]",
                "subject": "Important test",
                "body_text": "Same body",
                "body_html": None,
                "receive_time": datetime(2026, 4, 13, 12, 0, 0),
                "has_attachments": False,
                "is_read": True,
                "fingerprint": "fp-1",
            },
        ]
        updated_states = [
            {
                "mailbox": "INBOX",
                "role": "inbox",
                "include_in_sync": True,
                "last_uid": 20,
                "last_seen_at": datetime(2026, 4, 13, 12, 5, 0),
            },
            {
                "mailbox": "垃圾邮件",
                "role": "junk",
                "include_in_sync": True,
                "last_uid": 10,
                "last_seen_at": datetime(2026, 4, 13, 12, 5, 0),
            },
        ]

        with patch.object(imap_service, "AsyncSessionLocal", self.session_factory):
            inserted = await imap_service._merge_incoming_mailboxes(
                {
                    "id": "account-1",
                    "email": "owner@example.com",
                    "imap_host": "imap.example.com",
                    "imap_port": 993,
                },
                parsed_emails,
                updated_states,
            )

        self.assertEqual(inserted, 1)

        async with self.session_factory() as session:
            emails = (await session.execute(select(Email))).scalars().all()
            copies = (await session.execute(select(EmailFolderCopy))).scalars().all()
            states = (await session.execute(select(AccountFolderState))).scalars().all()

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0].folder, "INBOX")
        self.assertEqual(emails[0].uid, 20)
        self.assertTrue(emails[0].is_read)
        self.assertEqual(len(copies), 2)
        self.assertEqual(sorted(copy.mailbox for copy in copies), ["INBOX", "垃圾邮件"])
        self.assertEqual({state.mailbox for state in states}, {"INBOX", "垃圾邮件"})

    async def test_cleanup_all_mail_metadata_removes_all_only_emails_and_recomputes_remaining(self):
        await self._seed_account()

        async with self.session_factory() as session:
            session.add_all(
                [
                    AccountFolderState(
                        id="state-all",
                        account_id="account-1",
                        mailbox="[Gmail]/All Mail",
                        role="all",
                        include_in_sync=False,
                        last_uid=123,
                        last_seen_at=datetime(2026, 4, 13, 12, 0, 0),
                    ),
                    Email(
                        id="email-keep",
                        message_id="<keep@example.com>",
                        account_id="account-1",
                        uid=20,
                        sender="sender@example.com",
                        sender_name="Sender",
                        recipients="[]",
                        subject="Keep me",
                        body_text="Body",
                        body_html=None,
                        receive_time=datetime(2026, 4, 13, 12, 0, 0),
                        is_read=True,
                        has_attachments=False,
                        folder="[Gmail]/All Mail",
                    ),
                    Email(
                        id="email-drop",
                        message_id="<drop@example.com>",
                        account_id="account-1",
                        uid=30,
                        sender="sender@example.com",
                        sender_name="Sender",
                        recipients="[]",
                        subject="Drop me",
                        body_text="Body",
                        body_html=None,
                        receive_time=datetime(2026, 4, 13, 12, 5, 0),
                        is_read=False,
                        has_attachments=False,
                        folder="[Gmail]/All Mail",
                    ),
                    EmailFolderCopy(
                        id="copy-keep-all",
                        email_id="email-keep",
                        account_id="account-1",
                        mailbox="[Gmail]/All Mail",
                        role="all",
                        uid=200,
                        is_read=True,
                        last_synced_at=datetime(2026, 4, 13, 12, 0, 0),
                    ),
                    EmailFolderCopy(
                        id="copy-keep-inbox",
                        email_id="email-keep",
                        account_id="account-1",
                        mailbox="INBOX",
                        role="inbox",
                        uid=20,
                        is_read=False,
                        last_synced_at=datetime(2026, 4, 13, 12, 0, 0),
                    ),
                    EmailFolderCopy(
                        id="copy-drop-all",
                        email_id="email-drop",
                        account_id="account-1",
                        mailbox="[Gmail]/All Mail",
                        role="all",
                        uid=300,
                        is_read=False,
                        last_synced_at=datetime(2026, 4, 13, 12, 0, 0),
                    ),
                ]
            )
            await session.commit()

        with patch.object(database, "AsyncSessionLocal", self.session_factory):
            await database._cleanup_all_mail_metadata()

        async with self.session_factory() as session:
            emails = (await session.execute(select(Email).order_by(Email.id.asc()))).scalars().all()
            copies = (await session.execute(select(EmailFolderCopy).order_by(EmailFolderCopy.id.asc()))).scalars().all()
            states = (await session.execute(select(AccountFolderState))).scalars().all()

        self.assertEqual([email.id for email in emails], ["email-keep"])
        self.assertEqual(emails[0].folder, "INBOX")
        self.assertEqual(emails[0].uid, 20)
        self.assertFalse(emails[0].is_read)
        self.assertEqual([(copy.email_id, copy.role) for copy in copies], [("email-keep", "inbox")])
        self.assertEqual(states, [])


if __name__ == "__main__":
    unittest.main()
