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
from routers import emails as emails_router
from routers import send as send_router
from services.smtp_service import SendEmailResult


class SentReplyRouteTests(unittest.IsolatedAsyncioTestCase):
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

    async def _seed_source_email(self) -> tuple[str, str]:
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
            return account.id, email.id

    async def test_send_route_persists_sent_reply_on_success(self):
        account_id, _ = await self._seed_source_email()
        request = send_router.SendRequest(
            account_id=account_id,
            to="recipient@example.com",
            subject="Re: Important test",
            body="Reply body",
            reply_to_message_id="<source@example.com>",
        )
        send_result = SendEmailResult(
            account_id=account_id,
            message_id="<sent-1@example.com>",
            recipient="recipient@example.com",
            subject="Re: Important test",
            body_text="Reply body",
            sent_at=datetime(2026, 4, 13, 15, 5, 0),
            in_reply_to="<source@example.com>",
            references="<source@example.com>",
        )

        async with self.session_factory() as session:
            with patch.object(send_router, "send_email", return_value=send_result):
                response = await send_router.send(request, session=session)

        self.assertTrue(response.ok)
        self.assertEqual(response.sent_reply.message_id, "<sent-1@example.com>")

        async with self.session_factory() as session:
            rows = (await session.execute(select(SentReply))).scalars().all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].source_email_id, "email-1")
            self.assertEqual(rows[0].body_text, "Reply body")

    async def test_send_route_does_not_persist_sent_reply_on_failure(self):
        account_id, _ = await self._seed_source_email()
        request = send_router.SendRequest(
            account_id=account_id,
            to="recipient@example.com",
            subject="Re: Important test",
            body="Reply body",
            reply_to_message_id="<source@example.com>",
        )

        async with self.session_factory() as session:
            with patch.object(send_router, "send_email", side_effect=RuntimeError("smtp failure")):
                with self.assertRaises(Exception):
                    await send_router.send(request, session=session)

        async with self.session_factory() as session:
            rows = (await session.execute(select(SentReply))).scalars().all()
            self.assertEqual(rows, [])

    async def test_get_email_returns_sent_replies_sorted_by_sent_time(self):
        account_id, email_id = await self._seed_source_email()

        async with self.session_factory() as session:
            session.add_all(
                [
                    SentReply(
                        id="reply-2",
                        source_email_id=email_id,
                        account_id=account_id,
                        message_id="<sent-2@example.com>",
                        in_reply_to="<source@example.com>",
                        references="<source@example.com>",
                        recipient="recipient@example.com",
                        subject="Re: Important test",
                        body_text="Second reply",
                        sent_at=datetime(2026, 4, 13, 15, 10, 0),
                    ),
                    SentReply(
                        id="reply-1",
                        source_email_id=email_id,
                        account_id=account_id,
                        message_id="<sent-1@example.com>",
                        in_reply_to="<source@example.com>",
                        references="<source@example.com>",
                        recipient="recipient@example.com",
                        subject="Re: Important test",
                        body_text="First reply",
                        sent_at=datetime(2026, 4, 13, 15, 5, 0),
                    ),
                ]
            )
            await session.commit()

        async with self.session_factory() as session:
            detail = await emails_router.get_email(email_id, session=session)

        self.assertEqual([reply.id for reply in detail.sent_replies], ["reply-1", "reply-2"])
        self.assertEqual(detail.sent_replies[0].body_text, "First reply")
        self.assertEqual(detail.sent_replies[1].body_text, "Second reply")


if __name__ == "__main__":
    unittest.main()
