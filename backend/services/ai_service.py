"""
Ollama AI 服务。
模型：qwen3:4b
策略：
  - 批处理时强制 JSON 输出（format="json"）
  - temperature=0 保证格式稳定
  - 正文截断至 4800 字符（~1200 tokens），给 reasoning 留空间
  - system prompt 精简，控制在 200 字以内
"""
import json
import logging
from typing import Optional

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:4b"
BODY_MAX_CHARS = 4800  # 正文截断上限

# 默认 prompt 模板（用户可在设置中自定义，{role}/{focus}/{tone} 为占位符）
DEFAULT_ANALYSIS_PROMPT_PREFIX = (
    "你是邮件助手。角色：{role}，关注：{focus}。语气：{tone}。"
)
# JSON 格式要求永远追加（不可由用户删除，防止解析崩溃）
ANALYSIS_PROMPT_JSON_SUFFIX = (
    "\n分析邮件后，仅输出以下格式的纯JSON（不加任何额外文字）：\n"
    '{"importance_score":1-5,"is_important":true/false,"summary":"一句话核心摘要",'
    '"action_items":["待办1","待办2"],"ghost_reply_suggestion":"一句话回复建议"}'
)
DEFAULT_REPLY_PROMPT = (
    "你是专业邮件写作助手。你的身份：{role}。语气要求：{tone}。\n"
    "请将用户提供的草稿扩写为一封结构完整、语气专业的回复邮件。\n"
    "只输出邮件正文，不要包含主题行、称谓等格式提示语。"
)


class EmailAIResult(BaseModel):
    importance_score: int           # 1-5
    is_important: bool
    summary: str
    action_items: list[str]
    ghost_reply_suggestion: str


def _fill_prompt(template: str, role: str, focus: str, tone: str) -> str:
    """将 {role}/{focus}/{tone} 占位符替换为实际值（用 replace 避免与 JSON 大括号冲突）"""
    return (template
            .replace("{role}", role or "")
            .replace("{focus}", focus or "")
            .replace("{tone}", tone or "专业、客观、直接"))


def _build_system_prompt(role: str, focus: str, tone: str,
                         custom_prefix: str | None = None) -> str:
    prefix = custom_prefix if custom_prefix is not None else DEFAULT_ANALYSIS_PROMPT_PREFIX
    return _fill_prompt(prefix, role, focus, tone) + ANALYSIS_PROMPT_JSON_SUFFIX


def _truncate_body(body: str) -> str:
    if len(body) > BODY_MAX_CHARS:
        return body[:BODY_MAX_CHARS] + "\n...[正文已截断]"
    return body


async def analyze_email(
    subject: str,
    sender: str,
    body_text: str,
    role: str = "",
    focus: str = "",
    tone: str = "专业、客观、直接",
    model: str = OLLAMA_MODEL,
    analysis_system_prompt: str | None = None,
) -> Optional[EmailAIResult]:
    """
    调用 Ollama 分析单封邮件。
    返回 EmailAIResult，失败返回 None。
    """
    system_prompt = _build_system_prompt(role, focus, tone, custom_prefix=analysis_system_prompt)
    user_content = (
        f"发件人：{sender}\n"
        f"主题：{subject}\n"
        f"正文：\n{_truncate_body(body_text or '（正文为空）')}"
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
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]

        # 解析 JSON
        try:
            parsed = EmailAIResult.model_validate_json(content)
            # 保证 importance_score 在 1-5
            parsed.importance_score = max(1, min(5, parsed.importance_score))
            return parsed
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning("JSON 解析失败，尝试宽松解析: %s\n原始输出: %s", e, content[:200])
            # 宽松兜底：尝试从 content 中提取 JSON 块
            return _try_extract_json(content)

    except httpx.ConnectError:
        logger.error("Ollama 服务未启动，无法连接 %s", OLLAMA_BASE_URL)
        return None
    except httpx.HTTPStatusError as e:
        logger.error(
            "Ollama HTTP 错误 %s，模型='%s'，响应: %s",
            e.response.status_code, model, e.response.text
        )
        return None
    except Exception as e:
        logger.error("Ollama 调用异常（模型='%s'）: %s", model, e)
        return None


def _try_extract_json(text: str) -> Optional[EmailAIResult]:
    """尝试从文本中提取第一个 JSON 对象（应对模型输出带 markdown 的情况）"""
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
    tone: str = "专业、客观、直接",
    model: str = OLLAMA_MODEL,
    reply_system_prompt: str | None = None,
) -> str:
    """
    将草稿/幽灵文本扩写为完整专业邮件。
    返回扩写后的纯文本。
    """
    template = reply_system_prompt if reply_system_prompt is not None else DEFAULT_REPLY_PROMPT
    system_prompt = _fill_prompt(template, role, focus, tone)
    user_content = (
        f"原邮件主题：{subject}\n"
        f"原发件人：{original_sender}\n"
        f"草稿：{draft}"
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
    except httpx.HTTPStatusError as e:
        logger.error(
            "扩写回复 HTTP 错误 %s，模型='%s'，响应: %s",
            e.response.status_code, model, e.response.text
        )
        raise
    except Exception as e:
        logger.error("扩写回复失败（模型='%s'）: %s", model, e)
        raise


async def check_ollama_status() -> dict:
    """检查 Ollama 服务状态"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            model_loaded = any(OLLAMA_MODEL in m for m in models)
            return {
                "running": True,
                "model_available": model_loaded,
                "models": models,
            }
    except Exception:
        return {"running": False, "model_available": False, "models": []}
