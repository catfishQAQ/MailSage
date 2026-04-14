import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiosmtplib.email import flatten_message

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import smtp_service


class FakeSession:
    def __init__(self, account):
        self.account = account

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, account_id):
        return self.account


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.is_connected = False
        self.connect_calls = 0
        self.quit_calls = 0
        self.sent_messages: list[dict] = []
        self.__class__.instances.append(self)

    async def connect(self):
        self.connect_calls += 1
        self.is_connected = True

    async def send_message(self, message, *, sender, recipients):
        self.sent_messages.append(
            {
                "message": message,
                "sender": sender,
                "recipients": recipients,
            }
        )
        return {}, "OK"

    async def quit(self):
        self.quit_calls += 1
        self.is_connected = False


class SMTPServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeSMTP.instances.clear()
        self.account = SimpleNamespace(
            email="sender@example.com",
            display_name="\u53d1\u4ef6\u4eba",
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_use_ssl=True,
            encrypted_password="ciphertext",
        )

    async def _send_email(
        self,
        *,
        to: str = "\u6536\u4ef6\u4eba <recipient@example.com>",
        subject: str = "Re: \u91cd\u8981\u6d4b\u8bd5",
        body: str = "\u597d\u7684\uff0c\u6211\u5df2\u6536\u5230\u60a8\u7684\u90ae\u4ef6\u3002",
        reply_to_message_id: str | None = "<reply@example.com>",
        fqdn: str = "\u6211\u7684\u7535\u8111",
        hostname: str = "\u6211\u7684\u7535\u8111",
    ):
        with (
            patch.object(smtp_service, "AsyncSessionLocal", lambda: FakeSession(self.account)),
            patch.object(smtp_service, "decrypt", return_value="app-password"),
            patch.object(smtp_service.aiosmtplib, "SMTP", FakeSMTP),
            patch.object(smtp_service.socket, "getfqdn", return_value=fqdn),
            patch.object(smtp_service.socket, "gethostname", return_value=hostname),
        ):
            result = await smtp_service.send_email(
                account_id="account-1",
                to=to,
                subject=subject,
                body=body,
                reply_to_message_id=reply_to_message_id,
            )

        self.assertEqual(len(FakeSMTP.instances), 1)
        return FakeSMTP.instances[0], result

    async def test_unicode_system_hostname_uses_ascii_safe_local_hostname(self):
        client, result = await self._send_email(fqdn="\u6211\u7684\u7535\u8111", hostname="\u6211\u7684\u7535\u8111")

        self.assertTrue(client.kwargs["local_hostname"].isascii())
        self.assertNotEqual(client.kwargs["local_hostname"], "\u6211\u7684\u7535\u8111")
        self.assertEqual(client.connect_calls, 1)
        self.assertEqual(client.quit_calls, 1)
        self.assertEqual(result.recipient, "recipient@example.com")

    async def test_ascii_system_hostname_is_preserved(self):
        client, _ = await self._send_email(fqdn="mailbox.local", hostname="backup-host")

        self.assertEqual(client.kwargs["local_hostname"], "mailbox.local")

    async def test_chinese_subject_and_body_are_serializable(self):
        client, result = await self._send_email()
        sent = client.sent_messages[0]
        message = sent["message"]
        payload = message.get_payload()[0]
        serialized = flatten_message(message)

        self.assertEqual(sent["sender"], "sender@example.com")
        self.assertEqual(sent["recipients"], ["recipient@example.com"])
        self.assertEqual(payload.get_content_charset(), "utf-8")
        self.assertEqual(
            payload.get_payload(decode=True).decode("utf-8"),
            "\u597d\u7684\uff0c\u6211\u5df2\u6536\u5230\u60a8\u7684\u90ae\u4ef6\u3002",
        )
        self.assertIn(b"Subject: =?utf-8?", serialized)
        self.assertEqual(message["Message-ID"], result.message_id)

    async def test_reply_headers_are_preserved_in_result(self):
        reply_id = "<original-message@example.com>"
        client, result = await self._send_email(reply_to_message_id=reply_id)
        message = client.sent_messages[0]["message"]

        self.assertEqual(message["In-Reply-To"], reply_id)
        self.assertEqual(message["References"], reply_id)
        self.assertEqual(result.in_reply_to, reply_id)
        self.assertEqual(result.references, reply_id)


if __name__ == "__main__":
    unittest.main()
