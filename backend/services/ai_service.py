"""
Ollama-backed AI helpers for email analysis and reply expansion.
"""

import json
import logging
from typing import Optional

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:4b"
BODY_MAX_CHARS = 4800

SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}
DEFAULT_LANGUAGE = "en-US"
DEFAULT_TONES = {
    "zh-CN": "专业、客观、直接",
    "en-US": "professional, objective, direct",
}
DEFAULT_ANALYSIS_PROMPT_PREFIXES = {
    "zh-CN": "你是邮件助手。角色：{role}，关注：{focus}。语气：{tone}。",
    "en-US": "You are an email assistant. Role: {role}. Focus: {focus}. Tone: {tone}.",
}
ANALYSIS_PROMPT_JSON_SUFFIXES = {
    "zh-CN": (
        "\n分析邮件后，仅输出以下格式的纯JSON（不加任何额外文字）：\n"
        '{"importance_score":1-5,"is_important":true/false,"summary":"一句话核心摘要",'
        '"action_items":["待办1","待办2"],"ghost_reply_suggestion":"一句话回复建议"}'
    ),
    "en-US": (
        "\nAfter analyzing the email, output only pure JSON in this format "
        "(no extra text):\n"
        '{"importance_score":1-5,"is_important":true/false,"summary":"One-sentence summary",'
        '"action_items":["Action item 1","Action item 2"],'
        '"ghost_reply_suggestion":"One-sentence reply suggestion"}'
    ),
}
DEFAULT_REPLY_PROMPTS = {
    "zh-CN": (
        "你是专业邮件写作助手。你的身份：{role}。语气要求：{tone}。\n"
        "请将用户提供的草稿扩写为一封结构完整、语气专业的回复邮件。\n"
        "只输出邮件正文，不要包含主题行、称谓等格式提示语。"
    ),
    "en-US": (
        "You are a professional email writing assistant. Your role is {role}. "
        "Required tone: {tone}.\n"
        "Expand the user's draft into a complete, professional reply email.\n"
        "Output only the email body. Do not include a subject line or formatting instructions."
    ),
}
EMPTY_BODY_TEXT = {
    "zh-CN": "（正文为空）",
    "en-US": "(empty body)",
}
TRUNCATED_SUFFIX = {
    "zh-CN": "\n...[正文已截断]",
    "en-US": "\n...[body truncated]",
}
ANALYZE_USER_TEMPLATES = {
    "zh-CN": "发件人：{sender}\n主题：{subject}\n正文：\n{body}",
    "en-US": "Sender: {sender}\nSubject: {subject}\nBody:\n{body}",
}
EXPAND_USER_TEMPLATES = {
    "zh-CN": "原邮件主题：{subject}\n原发件人：{sender}\n草稿：{draft}",
    "en-US": "Original subject: {subject}\nOriginal sender: {sender}\nDraft: {draft}",
}


class EmailAIResult(BaseModel):
    importance_score: int
    is_important: bool
    summary: str
    action_items: list[str]
    ghost_reply_suggestion: str


def normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_default_analysis_prompt_prefix(language: str) -> str:
    return DEFAULT_ANALYSIS_PROMPT_PREFIXES[normalize_language(language)]


def get_analysis_prompt_json_suffix(language: str) -> str:
    return ANALYSIS_PROMPT_JSON_SUFFIXES[normalize_language(language)]


def get_default_reply_prompt(language: str) -> str:
    return DEFAULT_REPLY_PROMPTS[normalize_language(language)]


def get_default_tone(language: str) -> str:
    return DEFAULT_TONES[normalize_language(language)]


def _fill_prompt(template: str, role: str, focus: str, tone: str, language: str) -> str:
    return (
        template.replace("{role}", role or "")
        .replace("{focus}", focus or "")
        .replace("{tone}", tone or get_default_tone(language))
    )


def _build_system_prompt(
    role: str,
    focus: str,
    tone: str,
    language: str,
    custom_prefix: str | None = None,
) -> str:
    lang = normalize_language(language)
    prefix = custom_prefix if custom_prefix is not None else get_default_analysis_prompt_prefix(lang)
    return _fill_prompt(prefix, role, focus, tone, lang) + get_analysis_prompt_json_suffix(lang)


def _truncate_body(body: str, language: str) -> str:
    if len(body) > BODY_MAX_CHARS:
        return body[:BODY_MAX_CHARS] + TRUNCATED_SUFFIX[normalize_language(language)]
    return body


async def analyze_email(
    subject: str,
    sender: str,
    body_text: str,
    role: str = "",
    focus: str = "",
    tone: str = DEFAULT_TONES[DEFAULT_LANGUAGE],
    model: str = OLLAMA_MODEL,
    analysis_system_prompt: str | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> Optional[EmailAIResult]:
    lang = normalize_language(language)
    system_prompt = _build_system_prompt(
        role,
        focus,
        tone,
        lang,
        custom_prefix=analysis_system_prompt,
    )
    user_content = ANALYZE_USER_TEMPLATES[lang].format(
        sender=sender,
        subject=subject,
        body=_truncate_body(body_text or EMPTY_BODY_TEXT[lang], lang),
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": 512,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]

        try:
            parsed = EmailAIResult.model_validate_json(content)
            parsed.importance_score = max(1, min(5, parsed.importance_score))
            return parsed
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.warning("JSON parse failed, trying fallback: %s\nRaw output: %s", exc, content[:200])
            return _try_extract_json(content)
    except httpx.ConnectError:
        logger.error("Ollama is not reachable at %s", OLLAMA_BASE_URL)
        return None
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Ollama HTTP error %s for model '%s': %s",
            exc.response.status_code,
            model,
            exc.response.text,
        )
        return None
    except Exception as exc:
        logger.error("Ollama analysis failed for model '%s': %s", model, exc)
        return None


def _try_extract_json(text: str) -> Optional[EmailAIResult]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return EmailAIResult.model_validate_json(text[start:end])
    except Exception:
        return None


async def expand_reply(
    draft: str,
    subject: str,
    original_sender: str,
    role: str = "",
    focus: str = "",
    tone: str = DEFAULT_TONES[DEFAULT_LANGUAGE],
    model: str = OLLAMA_MODEL,
    reply_system_prompt: str | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    lang = normalize_language(language)
    template = reply_system_prompt if reply_system_prompt is not None else get_default_reply_prompt(lang)
    system_prompt = _fill_prompt(template, role, focus, tone, lang)
    user_content = EXPAND_USER_TEMPLATES[lang].format(
        subject=subject,
        sender=original_sender,
        draft=draft,
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Reply expansion HTTP error %s for model '%s': %s",
            exc.response.status_code,
            model,
            exc.response.text,
        )
        raise
    except Exception as exc:
        logger.error("Reply expansion failed for model '%s': %s", model, exc)
        raise


async def check_ollama_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = [model["name"] for model in resp.json().get("models", [])]
            model_loaded = any(OLLAMA_MODEL in model for model in models)
            return {
                "running": True,
                "model_available": model_loaded,
                "models": models,
            }
    except Exception:
        return {"running": False, "model_available": False, "models": []}
