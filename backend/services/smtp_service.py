"""SMTP sending service."""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from crypto import decrypt
from database import AsyncSessionLocal
from models import Account

logger = logging.getLogger(__name__)


async def send_email(
    account_id: str,
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: str | None = None,
) -> bool:
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

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{display_name or from_addr} <{from_addr}>"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to_message_id:
        msg["In-Reply-To"] = reply_to_message_id
        msg["References"] = reply_to_message_id

    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            use_tls=use_ssl,
            username=from_addr,
            password=password,
        )
        logger.info("邮件已发送至 %s，主题：%s", to, subject)
        return True
    except Exception as exc:
        logger.error("发信失败: %s", exc)
        raise
