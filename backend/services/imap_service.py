"""
IMAP 增量同步服务。
策略：
  - 首次（last_uid == 0）：拉取 INBOX 最近 200 封
  - 后续：只 FETCH UID > last_uid 的邮件
HTML 安全：使用 bleach 清理，防止 XSS
使用 stdlib imaplib（同步）+ asyncio.run_in_executor 以兼容 163.com 等需要 IMAP ID 命令的服务器。
"""
import asyncio
import base64
import email as email_lib
import imaplib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup
from sqlalchemy import select

from crypto import decrypt
from database import AsyncSessionLocal
from models import Account, Email, AIStatus

logger = logging.getLogger(__name__)

# bleach 白名单：允许的 HTML 标签和属性（防 XSS）
ALLOWED_TAGS = [
    "a", "b", "blockquote", "br", "code", "div", "em",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i",
    "img",
    "li", "ol", "p", "pre", "span", "strong", "table",
    "tbody", "td", "th", "thead", "tr", "ul",
]
ALLOWED_ATTRS = {
    "a":   ["href", "title"],
    "img": ["src", "alt", "width", "height"],
    "td":  ["colspan", "rowspan"],
    "th":  ["colspan", "rowspan"],
    "*":   ["style"],
}
_CLEAN_PROTOCOLS = ["http", "https", "data", "mailto"]
_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=[
    "color", "background-color", "background",
    "font-size", "font-weight", "font-style", "font-family",
    "text-align", "text-decoration",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "border", "border-collapse", "border-spacing",
    "width", "height", "max-width",
    "display", "vertical-align", "line-height",
])


def _decode_str(s: str | bytes | None) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _strip_non_visual_tags(html: str) -> str:
    """在 bleach 清洗前删除 <style>/<script> 及其内容。
    bleach.clean(strip=True) 只删标签本身会保留 CSS/JS 文本，导致正文乱码。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
    return str(soup)


def _extract_body(msg: email_lib.message.Message) -> tuple[str, str]:
    """返回 (body_text, body_html_sanitized)"""
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        # 第一遍：收集内嵌图片（CID），转为 base64 data URI
        cid_map: dict[str, str] = {}
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            cid = part.get("Content-ID", "").strip("<>")
            if ct.startswith("image/") and cid and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload and len(payload) <= 500_000:  # 跳过 >500KB 的大图
                    b64 = base64.b64encode(payload).decode()
                    cid_map[cid] = f"data:{ct};base64,{b64}"

        # 第二遍：提取文本和 HTML，替换 cid: 引用
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            if ct == "text/plain" and not body_text:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace") if payload else ""
            elif ct == "text/html" and not body_html:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                raw_html = payload.decode(charset, errors="replace") if payload else ""
                for cid, data_uri in cid_map.items():
                    raw_html = raw_html.replace(f"cid:{cid}", data_uri)
                body_html = bleach.clean(_strip_non_visual_tags(raw_html),
                                         tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                                         css_sanitizer=_CSS_SANITIZER,
                                         strip=True, protocols=_CLEAN_PROTOCOLS)
    else:
        ct = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace") if payload else ""
        if ct == "text/html":
            body_html = bleach.clean(_strip_non_visual_tags(text),
                                     tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                                     css_sanitizer=_CSS_SANITIZER,
                                     strip=True, protocols=_CLEAN_PROTOCOLS)
            _soup = BeautifulSoup(text, "html.parser")
            for _tag in _soup.find_all(["style", "script"]):
                _tag.decompose()
            body_text = _soup.get_text(separator="\n")
        else:
            body_text = text

    # 若只有 HTML，从 HTML 提取纯文本（先删除 style/script 节点，避免 CSS/JS 混入）
    if body_html and not body_text:
        soup = BeautifulSoup(body_html, "html.parser")
        for tag in soup.find_all(["style", "script"]):
            tag.decompose()
        body_text = soup.get_text(separator="\n")

    return body_text.strip(), body_html


def _has_attachments(msg: email_lib.message.Message) -> bool:
    for part in msg.walk():
        if "attachment" in str(part.get("Content-Disposition", "")):
            return True
    return False


def _do_sync_blocking(account_data: dict, password: str) -> tuple[list[dict], int]:
    """
    同步方式执行 IMAP 同步（在线程池 executor 中调用）。
    account_data 只含原始字段值（不跨线程传递 SQLAlchemy model）。
    返回 (parsed_emails, max_uid)。
    """
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)

    # 发送 IMAP ID 扩展命令（163.com / 网易系列 IMAP 服务器要求）
    # 注：不能用 _simple_command，其内部 _checkquote 会将括号列表转义为带引号的字符串，
    # 格式错误导致 163.com 服务器拒绝 ID 命令，进而使 SELECT INBOX 失败。
    # 使用 imap.send() 发送原始字节，完全绕过 _checkquote。
    try:
        imap.send(b'ZIDCMD1 ID ("name" "MailSage" "version" "1.0")\r\n')
        while True:
            line = imap.readline()
            if line.startswith(b'ZIDCMD1'):
                break
    except Exception:
        pass

    typ, _ = imap.select("INBOX")
    if typ != "OK":
        imap.logout()
        raise RuntimeError(f"SELECT INBOX failed: {typ}")

    last_uid: int = account_data["last_uid"]

    # 决定搜索范围
    if last_uid == 0:
        typ, data = imap.uid("search", None, "ALL")
        all_uids = data[0].decode().split() if data[0] else []
        uids_to_fetch = all_uids[-200:] if len(all_uids) > 200 else all_uids
    else:
        typ, data = imap.uid("search", None, f"UID {last_uid + 1}:*")
        uids_to_fetch = data[0].decode().split() if data[0] else []

    if not uids_to_fetch:
        imap.logout()
        return [], last_uid

    uid_set = ",".join(uids_to_fetch)

    # Step 1：仅拉 UID + FLAGS（无 literal，响应格式固定，可靠解析）
    # 不依赖字面量响应结构，避免 BODY.PEEK[] 和 RFC822 响应格式差异导致 UID=0
    uid_flags_map: dict[int, bool] = {}  # {uid: is_read}
    typ_f, flags_data = imap.uid("fetch", uid_set, "(UID FLAGS)")
    if flags_data:
        for item in flags_data:
            # imaplib 对无 literal 的响应通常返回 bytes，但部分服务器/版本返回 tuple
            if isinstance(item, bytes):
                line = item.decode(errors="replace")
            elif isinstance(item, tuple):
                line = item[0].decode(errors="replace")
            else:
                continue
            uid_match = re.search(r'UID\s+(\d+)', line, re.IGNORECASE)
            uid_val = int(uid_match.group(1)) if uid_match else 0
            if uid_val:
                uid_flags_map[uid_val] = "\\Seen" in line

    # Step 2：拉邮件正文（PEEK 不触发 \Seen）
    typ, fetch_data = imap.uid("fetch", uid_set, "(BODY.PEEK[])")

    parsed_emails: list[dict] = []
    max_uid = last_uid

    # Gmail 等服务器可能将 UID 放在字面量之后的 trailing 元素，需一并检查
    for idx, item in enumerate(fetch_data):
        if not isinstance(item, tuple):
            continue
        try:
            header_line = item[0].decode(errors="replace")
            raw = item[1]
            if not isinstance(raw, bytes):
                continue

            msg = email_lib.message_from_bytes(raw)

            # UID 可能在 item[0]，也可能在紧随其后的 trailing bytes 元素
            trailing = ""
            if idx + 1 < len(fetch_data) and isinstance(fetch_data[idx + 1], bytes):
                trailing = fetch_data[idx + 1].decode(errors="replace")
            uid_line = header_line + trailing

            uid_match = re.search(r'UID\s+(\d+)', uid_line, re.IGNORECASE)
            uid_val = int(uid_match.group(1)) if uid_match else 0

            # 从 Step 1 的映射获取 is_read；若映射里没有则回退到 False
            is_read = uid_flags_map.get(uid_val, False)

            message_id = msg.get("Message-ID", "").strip() or str(uuid.uuid4())
            subject = _decode_str(msg.get("Subject", "（无主题）"))
            sender_raw = _decode_str(msg.get("From", ""))
            sender_name, sender_addr = email_lib.utils.parseaddr(sender_raw)
            sender_name = _decode_str(sender_name) if sender_name else sender_addr

            date_str = msg.get("Date", "")
            try:
                receive_time = parsedate_to_datetime(date_str)
                if receive_time.tzinfo is None:
                    receive_time = receive_time.replace(tzinfo=timezone.utc)
                receive_time = receive_time.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                receive_time = datetime.utcnow()

            to_field = msg.get("To", "")
            recipients = json.dumps([to_field]) if to_field else "[]"

            body_text, body_html = _extract_body(msg)
            has_attach = _has_attachments(msg)

            parsed_emails.append({
                "id": message_id,
                "uid": uid_val,
                "sender": sender_addr,
                "sender_name": sender_name,
                "recipients": recipients,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "receive_time": receive_time,
                "has_attachments": has_attach,
                "is_read": is_read,
            })
            max_uid = max(max_uid, uid_val)

        except Exception as e:
            logger.warning("解析邮件失败: %s", e)
            continue

    imap.logout()
    return parsed_emails, max_uid


def _fetch_flags_blocking(account_data: dict, password: str, uids: list[int]) -> dict[int, bool]:
    """
    仅获取指定 UID 列表的 IMAP FLAGS（不下载正文），返回 {uid: is_read}。
    用于修正本地已存邮件的 is_read / ai_status。
    """
    if not uids:
        return {}
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    try:
        imap.send(b'ZIDCMD1 ID ("name" "MailSage" "version" "1.0")\r\n')
        while True:
            line = imap.readline()
            if line.startswith(b'ZIDCMD1'):
                break
    except Exception:
        pass
    typ, _ = imap.select("INBOX")
    if typ != "OK":
        imap.logout()
        return {}

    result: dict[int, bool] = {}
    for i in range(0, len(uids), 100):
        batch = uids[i:i + 100]
        uid_set = ",".join(str(u) for u in batch)
        try:
            typ2, data = imap.uid("fetch", uid_set, "(UID FLAGS)")
            logger.info("[flags] fetch typ=%s data_len=%d", typ2, len(data) if data else 0)
            if typ2 != "OK" or not data or data[0] is None:
                continue
            for item in data:
                raw_line = item if isinstance(item, bytes) else item[0]
                line = raw_line.decode(errors="replace")
                logger.info("[flags] raw item: %r", line)
                uid_match = re.search(r'UID\s+(\d+)', line, re.IGNORECASE)
                uid_val = int(uid_match.group(1)) if uid_match else 0
                if uid_val:
                    result[uid_val] = "\\Seen" in line
        except Exception as e:
            logger.warning("获取 FLAGS 失败 (batch %d): %s", i, e)

    logger.info("[flags] 解析结果 uid->is_read: %s", result)
    imap.logout()
    return result


def _mark_as_read_blocking(account_data: dict, password: str, uid: int):
    """在 IMAP 服务器上设置 \\Seen 标志（在 executor 中调用）"""
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    try:
        imap.send(b'ZIDCMD1 ID ("name" "MailSage" "version" "1.0")\r\n')
        while True:
            line = imap.readline()
            if line.startswith(b'ZIDCMD1'):
                break
    except Exception:
        pass
    typ, _ = imap.select("INBOX")
    if typ == "OK":
        imap.uid("store", str(uid), "+FLAGS", "\\Seen")
    imap.logout()


async def mark_as_read(account_id: str, uid: int):
    """在 IMAP 服务器标记指定邮件已读（uid=0 时跳过）"""
    if not uid:
        return
    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_id)
        if not account or not account.is_active:
            return
        password = decrypt(account.encrypted_password)
        account_data = {
            "email": account.email,
            "imap_host": account.imap_host,
            "imap_port": account.imap_port,
        }
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _mark_as_read_blocking, account_data, password, uid
        )
        logger.info("IMAP 标记已读: uid=%d account=%s", uid, account_data["email"])
    except Exception as e:
        logger.warning("IMAP 标记已读失败 uid=%d: %s", uid, e)


async def sync_account(account_id: str) -> int:
    """
    同步指定账号的 INBOX 邮件。
    返回新增邮件数量。
    """
    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_id)
        if not account or not account.is_active:
            return 0

        password = decrypt(account.encrypted_password)
        # 提取原始字段，避免跨线程传递 SQLAlchemy model
        account_data = {
            "id": account.id,
            "email": account.email,
            "imap_host": account.imap_host,
            "imap_port": account.imap_port,
            "last_uid": account.last_uid,
        }

    try:
        new_count = await _do_sync(account_data, password)
        logger.info("账号 %s 同步完成，新增 %d 封", account_data["email"], new_count)
        return new_count
    except Exception as e:
        logger.error("账号 %s 同步失败: %s", account_data["email"], e)
        return 0


async def _do_sync(account_data: dict, password: str) -> int:
    loop = asyncio.get_running_loop()
    parsed_emails, max_uid = await loop.run_in_executor(
        None, _do_sync_blocking, account_data, password
    )

    async with AsyncSessionLocal() as session:
        new_emails: list[Email] = []
        for data in parsed_emails:
            existing = await session.get(Email, data["id"])
            if existing:
                # 若 IMAP 已标记已读但本地还是未读，同步更新（只做 False→True）
                if data["is_read"] and not existing.is_read:
                    existing.is_read = True
                continue
            new_email = Email(
                id=data["id"],
                account_id=account_data["id"],
                uid=data["uid"],
                sender=data["sender"],
                sender_name=data["sender_name"],
                recipients=data["recipients"],
                subject=data["subject"],
                body_text=data["body_text"],
                body_html=data["body_html"],
                receive_time=data["receive_time"],
                has_attachments=data["has_attachments"],
                is_read=data["is_read"],
                # 原账号已读 → 不需要 AI 处理；未读 → 排队处理
                ai_status=AIStatus.completed if data["is_read"] else AIStatus.pending,
            )
            new_emails.append(new_email)

        if new_emails:
            session.add_all(new_emails)

        if max_uid > account_data["last_uid"]:
            acc = await session.get(Account, account_data["id"])
            if acc:
                acc.last_uid = max_uid

        # 双向同步已存邮件的已读状态：
        #   IMAP 已读 + 本地未读(pending) → is_read=True, ai_status=completed
        #   IMAP 未读 + 本地已读          → is_read=False, ai_status=pending（用户在原账号重新标为未读）
        all_emails_result = await session.execute(
            select(Email).where(
                Email.account_id == account_data["id"],
                Email.uid > 0,
            )
        )
        all_emails = all_emails_result.scalars().all()
        logger.info("[flags] 本地邮件总数=%d", len(all_emails))
        if all_emails:
            all_uids = [e.uid for e in all_emails]
            uid_flags = await loop.run_in_executor(
                None, _fetch_flags_blocking, account_data, password, all_uids
            )
            logger.info("[flags] IMAP 返回 flags 数=%d", len(uid_flags))
            changed = 0
            for email in all_emails:
                imap_read = uid_flags.get(email.uid)
                if imap_read is None:
                    continue  # IMAP 未返回该 UID（已删除/移走），跳过
                if imap_read and not email.is_read:
                    email.is_read = True
                    if email.ai_status == AIStatus.pending:
                        email.ai_status = AIStatus.completed
                    changed += 1
                elif not imap_read and email.is_read:
                    email.is_read = False
                    email.ai_status = AIStatus.pending
                    changed += 1
                    logger.info("[flags] 邮件重新标为未读: uid=%d subject=%r", email.uid, email.subject)
            logger.info("[flags] 状态变更邮件数=%d", changed)

        await session.commit()

    return len(new_emails)


async def sync_all_accounts():
    """定时任务入口：同步所有活跃账号"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Account).where(Account.is_active == True))
        accounts = result.scalars().all()

    tasks = [sync_account(acc.id) for acc in accounts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = sum(r for r in results if isinstance(r, int))
    logger.info("全量同步完成，共新增 %d 封邮件", total)
