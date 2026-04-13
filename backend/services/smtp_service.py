"""SMTP sending service."""

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import socket
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid, parseaddr

import aiosmtplib

from crypto import decrypt
from database import AsyncSessionLocal
from models import Account

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SendEmailResult:
    account_id: str
    message_id: str
    recipient: str
    subject: str
    body_text: str
    sent_at: datetime
    in_reply_to: str | None
    references: str | None


def _ascii_safe_hostname(candidate: str | None) -> str | None:
    if not candidate:
        return None

    normalized = candidate.strip().strip(".")
    if not normalized:
        return None

    try:
        normalized.encode("ascii")
        return normalized
    except UnicodeEncodeError:
        try:
            ascii_hostname = normalized.encode("idna").decode("ascii").strip(".")
        except UnicodeError:
            return None
        return ascii_hostname or None


def _get_smtp_local_hostname() -> str:
    for supplier in (socket.getfqdn, socket.gethostname):
        try:
            hostname = supplier()
        except OSError:
            continue

        ascii_hostname = _ascii_safe_hostname(hostname)
        if ascii_hostname:
            return ascii_hostname

    return "localhost"


async def send_email(
    account_id: str,
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: str | None = None,
) -> SendEmailResult:
    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_id)
        if not account:
            raise ValueError(f"账号 {account_id} 不存在")

        password = decrypt(account.encrypted_password)
        from_addr = account.email
        display_name = account.display_name
        smtp_host = account.smtp_host
        smtp_port = account.smtp_port
        use_ssl = account.smtp_use_ssl

    to_name, to_addr = parseaddr(to)
    if not to_addr:
        to_addr = to

    from_name = display_name if display_name and display_name != from_addr else ""

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, from_addr), charset="utf-8") if from_name else from_addr
    msg["To"] = formataddr((to_name, to_addr), charset="utf-8") if to_name else to_addr
    msg["Subject"] = Header(subject, "utf-8")
    message_id = make_msgid()
    msg["Message-ID"] = message_id
    if reply_to_message_id:
        msg["In-Reply-To"] = reply_to_message_id
        msg["References"] = reply_to_message_id

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if use_ssl or smtp_port == 465:
        tls_kwargs = {"use_tls": True}
    else:
        tls_kwargs = {"start_tls": True}

    local_hostname = _get_smtp_local_hostname()
    client = aiosmtplib.SMTP(
        hostname=smtp_host,
        port=smtp_port,
        username=from_addr,
        password=password,
        local_hostname=local_hostname,
        **tls_kwargs,
    )

    try:
        await client.connect()
    except Exception as exc:
        logger.error(
            "SMTP connect/EHLO failed for %s via %s:%s (local_hostname=%r): %s",
            from_addr,
            smtp_host,
            smtp_port,
            local_hostname,
            exc,
        )
        raise

    try:
        await client.send_message(
            msg,
            sender=from_addr,
            recipients=[to_addr],
        )
        logger.info("邮件已发送至 %s，主题：%s", to, subject)
        return SendEmailResult(
            account_id=account_id,
            message_id=message_id,
            recipient=to_addr,
            subject=subject,
            body_text=body,
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
            in_reply_to=reply_to_message_id,
            references=reply_to_message_id,
        )
    except Exception as exc:
        logger.error(
            "SMTP message send failed to %s via %s:%s: %s",
            to_addr,
            smtp_host,
            smtp_port,
            exc,
        )
        raise
    finally:
        with suppress(Exception):
            if client.is_connected:
                await client.quit()
