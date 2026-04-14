"""
IMAP sync service.

Highlights:
  - Sync all inbound-like mailboxes instead of only INBOX
  - Keep one logical email row and track per-folder IMAP copies separately
  - Detect common provider folders via special-use flags first, then name fallbacks
  - First sync for a mailbox backfills only recent history (14 days)
"""

import asyncio
import base64
import email as email_lib
import hashlib
import imaplib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup
from sqlalchemy import select

from crypto import decrypt
from database import AsyncSessionLocal
from models import (
    AIStatus,
    Account,
    AccountFolderState,
    Email,
    EmailFolderCopy,
    SentReply,
)

logger = logging.getLogger(__name__)

INITIAL_SYNC_DAYS = 14

ALLOWED_TAGS = [
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
]
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "width", "height"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "*": ["style"],
}
_CLEAN_PROTOCOLS = ["http", "https", "data", "mailto"]
_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "color",
        "background-color",
        "background",
        "font-size",
        "font-weight",
        "font-style",
        "font-family",
        "text-align",
        "text-decoration",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "border",
        "border-collapse",
        "border-spacing",
        "width",
        "height",
        "max-width",
        "display",
        "vertical-align",
        "line-height",
    ]
)

_COMMON_SENT_FOLDERS = {
    "sent",
    "sent items",
    "sent messages",
    "sent mail",
    "[gmail]/sent mail",
    "inbox.sent",
    "已发送",
    "已发送邮件",
}
_FOLDER_ROLE_BY_FLAG = {
    "\\sent": "sent",
    "\\drafts": "drafts",
    "\\junk": "junk",
    "\\trash": "trash",
    "\\archive": "archive",
    "\\all": "all",
}
_INCOMING_ROLES = {"inbox", "custom", "archive", "junk", "trash"}
_ROLE_PRIORITY = {
    "inbox": 50,
    "custom": 40,
    "archive": 30,
    "junk": 20,
    "trash": 10,
}
_NOSELECT_FLAGS = {"\\noselect", "\\nonexistent"}
_SENT_NAMES = {"sent", "sent items", "sent messages", "sent mail", "已发送", "已发送邮件"}
_DRAFT_NAMES = {"draft", "drafts", "草稿", "草稿箱"}
_OUTBOX_NAMES = {"outbox", "发件箱"}
_JUNK_NAMES = {"junk", "spam", "junk email", "bulk mail", "垃圾邮件"}
_TRASH_NAMES = {"trash", "bin", "deleted items", "deleted messages", "已删除", "已删除邮件"}
_ARCHIVE_NAMES = {"archive", "archives", "archived", "归档", "存档"}
_ALL_NAMES = {"all mail", "所有邮件"}
_INBOX_NAMES = {"inbox", "收件箱"}
_TEMPLATE_NAMES = {"template", "templates", "模板"}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _decode_str(s: str | bytes | None) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    parts = decode_header(s)
    result: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _decode_modified_utf7(value: str) -> str:
    if "&" not in value:
        return value

    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] != "&":
            next_idx = value.find("&", i)
            if next_idx == -1:
                next_idx = len(value)
            out.append(value[i:next_idx])
            i = next_idx
            continue

        end = value.find("-", i)
        if end == -1:
            out.append(value[i:])
            break
        if end == i + 1:
            out.append("&")
        else:
            encoded = value[i + 1 : end].replace(",", "/")
            encoded += "=" * (-len(encoded) % 4)
            try:
                out.append(base64.b64decode(encoded).decode("utf-16-be", errors="replace"))
            except Exception:
                out.append(value[i : end + 1])
        i = end + 1
    return "".join(out)


def mailbox_display_name(mailbox: str | None) -> str:
    if not mailbox:
        return "INBOX"
    return _decode_modified_utf7(mailbox).strip() or "INBOX"


def _strip_non_visual_tags(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
    return str(soup)


def _extract_body(msg: email_lib.message.Message) -> tuple[str, str]:
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        cid_map: dict[str, str] = {}
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            cid = part.get("Content-ID", "").strip("<>")
            if ct.startswith("image/") and cid and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload and len(payload) <= 500_000:
                    b64 = base64.b64encode(payload).decode()
                    cid_map[cid] = f"data:{ct};base64,{b64}"

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
                body_html = bleach.clean(
                    _strip_non_visual_tags(raw_html),
                    tags=ALLOWED_TAGS,
                    attributes=ALLOWED_ATTRS,
                    css_sanitizer=_CSS_SANITIZER,
                    strip=True,
                    protocols=_CLEAN_PROTOCOLS,
                )
    else:
        ct = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace") if payload else ""
        if ct == "text/html":
            body_html = bleach.clean(
                _strip_non_visual_tags(text),
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRS,
                css_sanitizer=_CSS_SANITIZER,
                strip=True,
                protocols=_CLEAN_PROTOCOLS,
            )
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup.find_all(["style", "script"]):
                tag.decompose()
            body_text = soup.get_text(separator="\n")
        else:
            body_text = text

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


def _send_imap_id(imap: imaplib.IMAP4_SSL):
    try:
        imap.send(b'ZIDCMD1 ID ("name" "MailSage" "version" "1.0")\r\n')
        while True:
            line = imap.readline()
            if line.startswith(b"ZIDCMD1"):
                break
    except Exception:
        pass


def _select_mailbox(imap: imaplib.IMAP4_SSL, mailbox: str):
    if mailbox.upper() == "INBOX":
        return imap.select("INBOX")
    escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
    return imap.select(f'"{escaped}"')


def _mailbox_name_variants(mailbox: str) -> set[str]:
    display = mailbox_display_name(mailbox).strip()
    if not display:
        return set()

    variants = {display.lower()}
    for separator in ("/", ".", "\\"):
        parts = [part.strip().lower() for part in display.split(separator) if part.strip()]
        variants.update(parts)
    return variants


def _classify_mailbox(flags: set[str], mailbox: str) -> tuple[str, bool]:
    lowered_flags = {flag.lower() for flag in flags}
    if lowered_flags & _NOSELECT_FLAGS:
        return "ignored", False

    for flag, role in _FOLDER_ROLE_BY_FLAG.items():
        if flag in lowered_flags:
            return role, role in _INCOMING_ROLES

    variants = _mailbox_name_variants(mailbox)
    if variants & _SENT_NAMES:
        return "sent", False
    if variants & _DRAFT_NAMES:
        return "drafts", False
    if variants & _OUTBOX_NAMES:
        return "outbox", False
    if variants & _JUNK_NAMES:
        return "junk", True
    if variants & _TRASH_NAMES:
        return "trash", True
    if variants & _ARCHIVE_NAMES:
        return "archive", True
    if variants & _ALL_NAMES:
        return "all", True
    if variants & _INBOX_NAMES:
        return "inbox", True
    if variants & _TEMPLATE_NAMES:
        return "template", False
    return "custom", True


def _parse_list_mailbox(item: bytes | str) -> tuple[set[str], str] | None:
    raw = item.decode(errors="replace") if isinstance(item, bytes) else item
    match = re.match(r'\((?P<flags>[^)]*)\)\s+"[^"]*"\s+(?P<mailbox>.+)$', raw.strip())
    if not match:
        return None

    mailbox = match.group("mailbox").strip()
    if mailbox.startswith('"') and mailbox.endswith('"'):
        mailbox = mailbox[1:-1].replace(r"\\", "\\").replace(r"\"", '"')

    flags = {flag.lower() for flag in match.group("flags").split() if flag}
    return flags, mailbox


def _find_sent_mailbox(imap: imaplib.IMAP4_SSL) -> str | None:
    typ, data = imap.list()
    if typ != "OK" or not data:
        return None

    fallback: str | None = None
    for item in data:
        parsed = _parse_list_mailbox(item)
        if not parsed:
            continue
        flags, mailbox = parsed
        if "\\sent" in flags:
            return mailbox
        if mailbox_display_name(mailbox).strip().lower() in _COMMON_SENT_FOLDERS and fallback is None:
            fallback = mailbox
    return fallback


def _discover_mailboxes(imap: imaplib.IMAP4_SSL) -> list[dict]:
    typ, data = imap.list()
    if typ != "OK" or not data:
        return []

    discovered: list[dict] = []
    for item in data:
        parsed = _parse_list_mailbox(item)
        if not parsed:
            continue
        flags, mailbox = parsed
        role, include_in_sync = _classify_mailbox(flags, mailbox)
        discovered.append(
            {
                "mailbox": mailbox,
                "display_name": mailbox_display_name(mailbox),
                "flags": flags,
                "role": role,
                "include_in_sync": include_in_sync,
            }
        )
    return discovered


def _extract_reference_ids(msg: email_lib.message.Message) -> list[str]:
    candidates: list[str] = []
    for header_name in ("In-Reply-To", "References"):
        raw = msg.get(header_name, "") or ""
        for message_id in re.findall(r"<[^>]+>", raw):
            normalized = _normalize_message_id(message_id)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
    return candidates


def _normalize_message_id(message_id: str | None) -> str | None:
    if not message_id:
        return None
    normalized = message_id.strip()
    return normalized.lower() if normalized else None


def _email_fingerprint(
    *,
    sender: str,
    subject: str,
    receive_time: datetime,
    body_text: str,
) -> str:
    payload = "\n".join(
        [
            sender.strip().lower(),
            subject.strip().lower(),
            receive_time.replace(microsecond=0).isoformat(),
            (body_text or "").strip().lower()[:512],
        ]
    )
    return hashlib.sha1(payload.encode("utf-8", errors="replace")).hexdigest()


def _folder_priority(role: str) -> int:
    return _ROLE_PRIORITY.get(role, 0)


def _choose_primary_copy(copies: list[EmailFolderCopy]) -> EmailFolderCopy | None:
    if not copies:
        return None
    return sorted(
        copies,
        key=lambda copy: (
            -_folder_priority(copy.role),
            mailbox_display_name(copy.mailbox).lower(),
            copy.uid,
        ),
    )[0]


def _parse_message_common(
    msg: email_lib.message.Message,
    *,
    uid_val: int,
    is_read: bool,
    mailbox: str,
    mailbox_role: str,
    fallback_id_prefix: str,
) -> dict:
    message_id = msg.get("Message-ID", "").strip() or f"{fallback_id_prefix}-{uuid.uuid4()}"
    normalized_message_id = _normalize_message_id(message_id)
    subject = _decode_str(msg.get("Subject", "(无主题)"))
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
        receive_time = _utcnow_naive()

    to_field = msg.get("To", "")
    recipients = json.dumps([to_field]) if to_field else "[]"
    body_text, body_html = _extract_body(msg)

    return {
        "id": str(uuid.uuid4()),
        "message_id": message_id,
        "normalized_message_id": normalized_message_id,
        "uid": uid_val,
        "mailbox": mailbox,
        "mailbox_role": mailbox_role,
        "sender": sender_addr,
        "sender_name": sender_name,
        "recipients": recipients,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "receive_time": receive_time,
        "has_attachments": _has_attachments(msg),
        "is_read": is_read,
        "fingerprint": _email_fingerprint(
            sender=sender_addr,
            subject=subject,
            receive_time=receive_time,
            body_text=body_text,
        ),
    }


def _search_initial_uids(imap: imaplib.IMAP4_SSL) -> tuple[list[str], int]:
    typ_all, data_all = imap.uid("search", None, "ALL")
    all_uids = data_all[0].decode().split() if typ_all == "OK" and data_all and data_all[0] else []
    max_uid = int(all_uids[-1]) if all_uids else 0

    cutoff = (_utcnow_naive() - timedelta(days=INITIAL_SYNC_DAYS)).strftime("%d-%b-%Y")
    typ_recent, data_recent = imap.uid("search", None, "SINCE", cutoff)
    recent_uids = (
        data_recent[0].decode().split()
        if typ_recent == "OK" and data_recent and data_recent[0]
        else []
    )
    return recent_uids, max_uid


def _search_incremental_uids(imap: imaplib.IMAP4_SSL, last_uid: int) -> tuple[list[str], int]:
    typ, data = imap.uid("search", None, f"UID {last_uid + 1}:*")
    uids = data[0].decode().split() if typ == "OK" and data and data[0] else []
    max_uid = int(uids[-1]) if uids else last_uid
    return uids, max_uid


def _fetch_uid_flags(imap: imaplib.IMAP4_SSL, uids_to_fetch: list[str]) -> dict[int, bool]:
    uid_set = ",".join(uids_to_fetch)
    uid_flags_map: dict[int, bool] = {}
    _, flags_data = imap.uid("fetch", uid_set, "(UID FLAGS)")
    if not flags_data:
        return uid_flags_map

    for item in flags_data:
        if isinstance(item, bytes):
            line = item.decode(errors="replace")
        elif isinstance(item, tuple):
            line = item[0].decode(errors="replace")
        else:
            continue
        uid_match = re.search(r"UID\s+(\d+)", line, re.IGNORECASE)
        uid_val = int(uid_match.group(1)) if uid_match else 0
        if uid_val:
            uid_flags_map[uid_val] = "\\Seen" in line
    return uid_flags_map


def _fetch_mailbox_messages(
    imap: imaplib.IMAP4_SSL,
    *,
    mailbox: str,
    mailbox_role: str,
    last_uid: int,
) -> tuple[list[dict], int]:
    typ, _ = _select_mailbox(imap, mailbox)
    if typ != "OK":
        logger.warning("SELECT mailbox failed: %s", mailbox_display_name(mailbox))
        return [], last_uid

    if last_uid > 0:
        uids_to_fetch, max_uid = _search_incremental_uids(imap, last_uid)
    else:
        uids_to_fetch, max_uid = _search_initial_uids(imap)

    if not uids_to_fetch:
        return [], max_uid

    uid_flags_map = _fetch_uid_flags(imap, uids_to_fetch)
    uid_set = ",".join(uids_to_fetch)
    _, fetch_data = imap.uid("fetch", uid_set, "(BODY.PEEK[])")

    parsed_emails: list[dict] = []
    for idx, item in enumerate(fetch_data):
        if not isinstance(item, tuple):
            continue
        try:
            header_line = item[0].decode(errors="replace")
            raw = item[1]
            if not isinstance(raw, bytes):
                continue

            msg = email_lib.message_from_bytes(raw)

            trailing = ""
            if idx + 1 < len(fetch_data) and isinstance(fetch_data[idx + 1], bytes):
                trailing = fetch_data[idx + 1].decode(errors="replace")
            uid_line = header_line + trailing

            uid_match = re.search(r"UID\s+(\d+)", uid_line, re.IGNORECASE)
            uid_val = int(uid_match.group(1)) if uid_match else 0
            is_read = uid_flags_map.get(uid_val, False)

            parsed = _parse_message_common(
                msg,
                uid_val=uid_val,
                is_read=is_read,
                mailbox=mailbox,
                mailbox_role=mailbox_role,
                fallback_id_prefix=f"mailbox-{mailbox}",
            )

            parsed_emails.append(parsed)
        except Exception as exc:
            logger.warning("解析邮件失败 (%s): %s", mailbox_display_name(mailbox), exc)
            continue

    return parsed_emails, max_uid


def _sync_incoming_mailboxes_blocking(
    account_data: dict,
    password: str,
) -> tuple[list[dict], list[dict]]:
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    _send_imap_id(imap)

    discovered_mailboxes = _discover_mailboxes(imap)
    known_states = account_data.get("folder_states", {})
    parsed_emails: list[dict] = []
    updated_states: list[dict] = []

    for mailbox_info in discovered_mailboxes:
        mailbox = mailbox_info["mailbox"]
        prior = known_states.get(mailbox, {})
        last_uid = int(prior.get("last_uid") or 0)
        mailbox_last_uid = last_uid

        if mailbox_info["include_in_sync"]:
            mailbox_emails, mailbox_last_uid = _fetch_mailbox_messages(
                imap,
                mailbox=mailbox,
                mailbox_role=mailbox_info["role"],
                last_uid=last_uid,
            )
            parsed_emails.extend(mailbox_emails)

        if mailbox_info["role"] != "all":
            updated_states.append(
                {
                    "mailbox": mailbox,
                    "role": mailbox_info["role"],
                    "include_in_sync": mailbox_info["include_in_sync"],
                    "last_uid": mailbox_last_uid,
                    "last_seen_at": _utcnow_naive(),
                }
            )

    imap.logout()
    return parsed_emails, updated_states


def _fetch_sent_messages_blocking(
    account_data: dict,
    password: str,
) -> tuple[list[dict], int, str | None]:
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    _send_imap_id(imap)

    sent_mailbox = account_data.get("sent_folder")
    if sent_mailbox:
        typ, _ = _select_mailbox(imap, sent_mailbox)
        if typ != "OK":
            sent_mailbox = None

    if not sent_mailbox:
        sent_mailbox = _find_sent_mailbox(imap)
        if not sent_mailbox:
            imap.logout()
            return [], account_data.get("sent_last_uid", 0), None
        typ, _ = _select_mailbox(imap, sent_mailbox)
        if typ != "OK":
            imap.logout()
            return [], account_data.get("sent_last_uid", 0), None

    last_uid: int = account_data.get("sent_last_uid", 0)
    if last_uid == 0:
        typ, data = imap.uid("search", None, "ALL")
        all_uids = data[0].decode().split() if typ == "OK" and data and data[0] else []
        uids_to_fetch = all_uids[-200:] if len(all_uids) > 200 else all_uids
        max_uid = int(all_uids[-1]) if all_uids else 0
    else:
        uids_to_fetch, max_uid = _search_incremental_uids(imap, last_uid)

    if not uids_to_fetch:
        imap.logout()
        return [], max_uid or last_uid, sent_mailbox

    uid_set = ",".join(uids_to_fetch)
    _, fetch_data = imap.uid("fetch", uid_set, "(BODY.PEEK[])")

    parsed_sent: list[dict] = []
    max_seen_uid = max_uid or last_uid

    for idx, item in enumerate(fetch_data):
        if not isinstance(item, tuple):
            continue
        try:
            header_line = item[0].decode(errors="replace")
            raw = item[1]
            if not isinstance(raw, bytes):
                continue

            msg = email_lib.message_from_bytes(raw)

            trailing = ""
            if idx + 1 < len(fetch_data) and isinstance(fetch_data[idx + 1], bytes):
                trailing = fetch_data[idx + 1].decode(errors="replace")
            uid_line = header_line + trailing

            uid_match = re.search(r"UID\s+(\d+)", uid_line, re.IGNORECASE)
            uid_val = int(uid_match.group(1)) if uid_match else 0
            max_seen_uid = max(max_seen_uid, uid_val)

            message_id = msg.get("Message-ID", "").strip() or str(uuid.uuid4())
            recipient_raw = _decode_str(msg.get("To", ""))
            _, recipient_addr = email_lib.utils.parseaddr(recipient_raw)
            recipient = recipient_addr or recipient_raw
            subject = _decode_str(msg.get("Subject", "(无主题)"))
            body_text, _ = _extract_body(msg)

            date_str = msg.get("Date", "")
            try:
                sent_time = parsedate_to_datetime(date_str)
                if sent_time.tzinfo is None:
                    sent_time = sent_time.replace(tzinfo=timezone.utc)
                sent_time = sent_time.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                sent_time = _utcnow_naive()

            parsed_sent.append(
                {
                    "id": str(uuid.uuid4()),
                    "message_id": message_id,
                    "in_reply_to": _normalize_message_id(msg.get("In-Reply-To", "").strip() or None),
                    "references": msg.get("References", "").strip() or None,
                    "candidate_source_message_ids": _extract_reference_ids(msg),
                    "recipient": recipient,
                    "subject": subject,
                    "body_text": body_text,
                    "sent_at": sent_time,
                }
            )
        except Exception as exc:
            logger.warning("解析已发送邮件失败: %s", exc)
            continue

    imap.logout()
    return parsed_sent, max_seen_uid, sent_mailbox


def _fetch_copy_flags_blocking(
    account_data: dict,
    password: str,
    uids_by_mailbox: dict[str, list[int]],
) -> dict[tuple[str, int], bool]:
    result: dict[tuple[str, int], bool] = {}
    if not uids_by_mailbox:
        return result

    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    _send_imap_id(imap)

    for mailbox, uids in uids_by_mailbox.items():
        if not uids:
            continue
        typ, _ = _select_mailbox(imap, mailbox)
        if typ != "OK":
            continue
        for i in range(0, len(uids), 100):
            batch = uids[i : i + 100]
            uid_set = ",".join(str(uid) for uid in batch)
            try:
                typ2, data = imap.uid("fetch", uid_set, "(UID FLAGS)")
                if typ2 != "OK" or not data or data[0] is None:
                    continue
                for item in data:
                    raw_line = item if isinstance(item, bytes) else item[0]
                    line = raw_line.decode(errors="replace")
                    uid_match = re.search(r"UID\s+(\d+)", line, re.IGNORECASE)
                    uid_val = int(uid_match.group(1)) if uid_match else 0
                    if uid_val:
                        result[(mailbox, uid_val)] = "\\Seen" in line
            except Exception as exc:
                logger.warning("获取 FLAGS 失败 (%s batch %d): %s", mailbox_display_name(mailbox), i, exc)

    imap.logout()
    return result


def _mark_as_read_blocking(account_data: dict, password: str, mailbox: str, uid: int):
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    _send_imap_id(imap)
    typ, _ = _select_mailbox(imap, mailbox)
    if typ == "OK":
        imap.uid("store", str(uid), "+FLAGS", "\\Seen")
    imap.logout()


def _mark_many_as_read_blocking(
    account_data: dict,
    password: str,
    mailbox_uids: dict[str, list[int]],
):
    imap = imaplib.IMAP4_SSL(account_data["imap_host"], account_data["imap_port"])
    imap.login(account_data["email"], password)
    _send_imap_id(imap)
    try:
        for mailbox, uids in mailbox_uids.items():
            if not uids:
                continue
            typ, _ = _select_mailbox(imap, mailbox)
            if typ != "OK":
                continue
            for i in range(0, len(uids), 100):
                batch = sorted({uid for uid in uids[i : i + 100] if uid})
                if not batch:
                    continue
                imap.uid("store", ",".join(str(uid) for uid in batch), "+FLAGS", "\\Seen")
    finally:
        imap.logout()


async def mark_as_read(account_id: str, uid: int, mailbox: str | None = None):
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
            None,
            _mark_as_read_blocking,
            account_data,
            password,
            mailbox or "INBOX",
            uid,
        )
        logger.info("IMAP 标记已读: mailbox=%s uid=%d account=%s", mailbox or "INBOX", uid, account_data["email"])
    except Exception as exc:
        logger.warning("IMAP 标记已读失败 mailbox=%s uid=%d: %s", mailbox or "INBOX", uid, exc)


async def mark_copies_as_read(account_id: str, copies: list[tuple[str, int]]) -> int:
    if not copies:
        return 0

    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_id)
        if not account or not account.is_active:
            return 0
        password = decrypt(account.encrypted_password)
        account_data = {
            "email": account.email,
            "imap_host": account.imap_host,
            "imap_port": account.imap_port,
        }

    mailbox_uids: dict[str, list[int]] = {}
    for mailbox, uid in copies:
        if not uid:
            continue
        mailbox_uids.setdefault(mailbox or "INBOX", []).append(uid)

    if not mailbox_uids:
        return 0

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            _mark_many_as_read_blocking,
            account_data,
            password,
            mailbox_uids,
        )
        updated_count = sum(len(set(uids)) for uids in mailbox_uids.values())
        logger.info("IMAP 批量标记已读: account=%s copies=%d", account_data["email"], updated_count)
        return updated_count
    except Exception as exc:
        logger.warning("IMAP 批量标记已读失败 account=%s: %s", account_data["email"], exc)
        return 0


def _apply_email_copy_aggregates(
    email_objs: dict[str, Email],
    copies_by_email_id: dict[str, list[EmailFolderCopy]],
):
    for email_id, copies in copies_by_email_id.items():
        email_obj = email_objs.get(email_id)
        if email_obj is None or not copies:
            continue

        primary_copy = _choose_primary_copy(copies)
        if primary_copy is not None:
            email_obj.folder = primary_copy.mailbox
            email_obj.uid = primary_copy.uid

        is_read = any(copy.is_read for copy in copies)
        if is_read and not email_obj.is_read:
            email_obj.is_read = True
            if email_obj.ai_status == AIStatus.pending:
                email_obj.ai_status = AIStatus.completed
        elif not is_read and email_obj.is_read:
            email_obj.is_read = False
            if email_obj.ai_status == AIStatus.completed:
                email_obj.ai_status = AIStatus.pending


async def _merge_incoming_mailboxes(
    account_data: dict,
    parsed_emails: list[dict],
    updated_states: list[dict],
) -> int:
    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_data["id"])
        if account is None:
            return 0

        folder_state_result = await session.execute(
            select(AccountFolderState).where(AccountFolderState.account_id == account.id)
        )
        folder_states = {state.mailbox: state for state in folder_state_result.scalars().all()}
        for state_data in updated_states:
            state = folder_states.get(state_data["mailbox"])
            if state is None:
                state = AccountFolderState(
                    id=str(uuid.uuid4()),
                    account_id=account.id,
                    mailbox=state_data["mailbox"],
                )
                session.add(state)
                folder_states[state.mailbox] = state
            state.role = state_data["role"]
            state.include_in_sync = state_data["include_in_sync"]
            state.last_uid = state_data["last_uid"]
            state.last_seen_at = state_data["last_seen_at"]

        email_result = await session.execute(select(Email).where(Email.account_id == account.id))
        existing_emails = email_result.scalars().all()
        emails_by_id = {email.id: email for email in existing_emails}
        emails_by_message_id = {
            normalized: email
            for email in existing_emails
            if (normalized := _normalize_message_id(email.message_id))
        }
        emails_by_fingerprint = {
            _email_fingerprint(
                sender=email.sender or "",
                subject=email.subject or "",
                receive_time=email.receive_time,
                body_text=email.body_text or "",
            ): email
            for email in existing_emails
        }

        copy_result = await session.execute(
            select(EmailFolderCopy).where(EmailFolderCopy.account_id == account.id)
        )
        existing_copies = copy_result.scalars().all()
        copies_by_key = {(copy.mailbox, copy.uid): copy for copy in existing_copies}
        copies_by_email_id: dict[str, list[EmailFolderCopy]] = {}
        for copy in existing_copies:
            copies_by_email_id.setdefault(copy.email_id, []).append(copy)

        created_count = 0
        now = _utcnow_naive()

        for data in parsed_emails:
            existing_email = None
            if data["normalized_message_id"]:
                existing_email = emails_by_message_id.get(data["normalized_message_id"])
            if existing_email is None:
                existing_email = emails_by_fingerprint.get(data["fingerprint"])

            if existing_email is None:
                existing_email = Email(
                    id=data["id"],
                    message_id=data["message_id"],
                    account_id=account.id,
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
                    folder=data["mailbox"],
                    ai_status=AIStatus.completed if data["is_read"] else AIStatus.pending,
                )
                session.add(existing_email)
                emails_by_id[existing_email.id] = existing_email
                if data["normalized_message_id"]:
                    emails_by_message_id[data["normalized_message_id"]] = existing_email
                emails_by_fingerprint[data["fingerprint"]] = existing_email
                copies_by_email_id.setdefault(existing_email.id, [])
                created_count += 1
            else:
                if data["normalized_message_id"] and not _normalize_message_id(existing_email.message_id):
                    existing_email.message_id = data["message_id"]
                if data["is_read"] and not existing_email.is_read:
                    existing_email.is_read = True
                    if existing_email.ai_status == AIStatus.pending:
                        existing_email.ai_status = AIStatus.completed
                if not existing_email.body_text and data["body_text"]:
                    existing_email.body_text = data["body_text"]
                if not existing_email.body_html and data["body_html"]:
                    existing_email.body_html = data["body_html"]
                if not existing_email.sender_name and data["sender_name"]:
                    existing_email.sender_name = data["sender_name"]
                existing_email.has_attachments = existing_email.has_attachments or data["has_attachments"]

            copy_key = (data["mailbox"], data["uid"])
            copy = copies_by_key.get(copy_key)
            if copy is None:
                copy = EmailFolderCopy(
                    id=str(uuid.uuid4()),
                    email_id=existing_email.id,
                    account_id=account.id,
                    mailbox=data["mailbox"],
                    role=data["mailbox_role"],
                    uid=data["uid"],
                    is_read=data["is_read"],
                    last_synced_at=now,
                )
                session.add(copy)
                copies_by_key[copy_key] = copy
                copies_by_email_id.setdefault(existing_email.id, []).append(copy)
            else:
                copy.email_id = existing_email.id
                copy.role = data["mailbox_role"]
                copy.is_read = data["is_read"]
                copy.last_synced_at = now
                if copy not in copies_by_email_id.setdefault(existing_email.id, []):
                    copies_by_email_id[existing_email.id].append(copy)

        _apply_email_copy_aggregates(emails_by_id, copies_by_email_id)

        inbox_state = folder_states.get("INBOX")
        if inbox_state is not None:
            account.last_uid = inbox_state.last_uid or 0

        await session.commit()
        return created_count


async def _refresh_folder_copy_flags(account_data: dict, password: str):
    async with AsyncSessionLocal() as session:
        copy_result = await session.execute(
            select(EmailFolderCopy).where(EmailFolderCopy.account_id == account_data["id"])
        )
        copies = copy_result.scalars().all()
        if not copies:
            return
        uids_by_mailbox: dict[str, list[int]] = {}
        for copy in copies:
            uids_by_mailbox.setdefault(copy.mailbox, []).append(copy.uid)

    loop = asyncio.get_running_loop()
    flags_map = await loop.run_in_executor(
        None,
        _fetch_copy_flags_blocking,
        account_data,
        password,
        uids_by_mailbox,
    )

    async with AsyncSessionLocal() as session:
        copy_result = await session.execute(
            select(EmailFolderCopy).where(EmailFolderCopy.account_id == account_data["id"])
        )
        copies = copy_result.scalars().all()
        if not copies:
            return

        email_ids = {copy.email_id for copy in copies}
        email_result = await session.execute(select(Email).where(Email.id.in_(email_ids)))
        emails = {email.id: email for email in email_result.scalars().all()}
        copies_by_email_id: dict[str, list[EmailFolderCopy]] = {}

        for copy in copies:
            new_is_read = flags_map.get((copy.mailbox, copy.uid))
            if new_is_read is not None:
                copy.is_read = new_is_read
                copy.last_synced_at = _utcnow_naive()
            copies_by_email_id.setdefault(copy.email_id, []).append(copy)

        _apply_email_copy_aggregates(emails, copies_by_email_id)
        await session.commit()


async def _merge_sent_replies(
    account_id: str,
    parsed_sent_messages: list[dict],
    sent_last_uid: int,
    sent_folder: str | None,
) -> int:
    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_id)
        if not account:
            return 0

        if sent_folder:
            account.sent_folder = sent_folder
        if sent_last_uid > (account.sent_last_uid or 0):
            account.sent_last_uid = sent_last_uid

        if not parsed_sent_messages:
            await session.commit()
            return 0

        message_ids = [item["message_id"] for item in parsed_sent_messages if item.get("message_id")]
        existing_result = await session.execute(
            select(SentReply.message_id).where(
                SentReply.account_id == account_id,
                SentReply.message_id.in_(message_ids),
            )
        )
        existing_message_ids = set(existing_result.scalars().all())

        candidate_source_ids = {
            candidate
            for item in parsed_sent_messages
            for candidate in item.get("candidate_source_message_ids", [])
        }
        source_emails_by_message_id: dict[str, Email] = {}
        if candidate_source_ids:
            source_result = await session.execute(
                select(Email).where(
                    Email.account_id == account_id,
                    Email.message_id.in_(candidate_source_ids),
                )
            )
            source_emails_by_message_id = {
                normalized: email
                for email in source_result.scalars().all()
                if (normalized := _normalize_message_id(email.message_id))
            }

        inserted = 0
        for item in parsed_sent_messages:
            if item["message_id"] in existing_message_ids:
                continue

            source_email = None
            for candidate in item.get("candidate_source_message_ids", []):
                source_email = source_emails_by_message_id.get(candidate)
                if source_email is not None:
                    break

            if source_email is None:
                continue

            session.add(
                SentReply(
                    id=item["id"],
                    source_email_id=source_email.id,
                    account_id=account_id,
                    message_id=item["message_id"],
                    in_reply_to=item.get("in_reply_to"),
                    references=item.get("references"),
                    recipient=item["recipient"],
                    subject=item["subject"],
                    body_text=item["body_text"],
                    sent_at=item["sent_at"],
                    source="synced",
                )
            )
            inserted += 1

        await session.commit()
        return inserted


async def _sync_sent_replies(account_data: dict, password: str) -> int:
    loop = asyncio.get_running_loop()
    parsed_sent_messages, sent_last_uid, sent_folder = await loop.run_in_executor(
        None,
        _fetch_sent_messages_blocking,
        account_data,
        password,
    )
    return await _merge_sent_replies(
        account_id=account_data["id"],
        parsed_sent_messages=parsed_sent_messages,
        sent_last_uid=sent_last_uid,
        sent_folder=sent_folder,
    )


async def _do_sync(account_data: dict, password: str) -> int:
    loop = asyncio.get_running_loop()
    parsed_emails, updated_states = await loop.run_in_executor(
        None,
        _sync_incoming_mailboxes_blocking,
        account_data,
        password,
    )
    new_count = await _merge_incoming_mailboxes(account_data, parsed_emails, updated_states)
    await _refresh_folder_copy_flags(account_data, password)
    return new_count


async def sync_account(account_id: str) -> int:
    async with AsyncSessionLocal() as session:
        account = await session.get(Account, account_id)
        if not account or not account.is_active:
            return 0

        password = decrypt(account.encrypted_password)
        folder_state_result = await session.execute(
            select(AccountFolderState).where(AccountFolderState.account_id == account.id)
        )
        folder_states = {
            state.mailbox: {
                "last_uid": state.last_uid,
                "role": state.role,
                "include_in_sync": state.include_in_sync,
            }
            for state in folder_state_result.scalars().all()
        }
        account_data = {
            "id": account.id,
            "email": account.email,
            "imap_host": account.imap_host,
            "imap_port": account.imap_port,
            "last_uid": account.last_uid,
            "folder_states": folder_states,
            "sent_last_uid": account.sent_last_uid,
            "sent_folder": account.sent_folder,
        }

    try:
        new_count = await _do_sync(account_data, password)
        sent_count = await _sync_sent_replies(account_data, password)
        logger.info(
            "账号 %s 同步完成，收件新增 %d 封，回信导入 %d 封",
            account_data["email"],
            new_count,
            sent_count,
        )
        return new_count
    except Exception as exc:
        logger.error("账号 %s 同步失败: %s", account_data["email"], exc)
        return 0


async def sync_all_accounts():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Account).where(Account.is_active == True))
        accounts = result.scalars().all()

    tasks = [sync_account(acc.id) for acc in accounts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = sum(result for result in results if isinstance(result, int))
    logger.info("全量同步完成，共新增 %d 封邮件", total)
