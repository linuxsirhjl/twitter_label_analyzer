"""LLM 分类器：调用模型做标签判定与画像生成。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from openai import OpenAI

from app.models import UserAnalysisInput
from app.settings import get_config
from app.utils.json_utils import parse_json_safe

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "classify_user.txt"


def _get_client() -> OpenAI:
    cfg = get_config()
    model_cfg = cfg.get("model", {})
    base_url: str | None = model_cfg.get("base_url")
    api_key: str = model_cfg.get("_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    timeout = float(model_cfg.get("timeout", 120))

    if not api_key:
        # 内网服务不校验 key
        api_key = "local"

    http_timeout = httpx.Timeout(timeout, connect=15.0)
    return OpenAI(api_key=api_key, base_url=base_url, timeout=http_timeout)


def _build_user_prompt(analysis_input: UserAnalysisInput, rule_labels: list[str]) -> str:
    """构建发给模型的用户消息。"""
    user = analysis_input.user
    cfg = get_config()
    analysis_cfg = cfg.get("analysis", {})
    max_len = int(analysis_cfg.get("max_text_length", 1000))

    lines = [
        "## 用户基础资料",
        f"账号: {user.account}  账号ID: {user.account_id}  昵称: {user.nickname}",
        f"简介: {user.bio or '（无）'}",
        f"关注者: {user.followers_count}  帖子数: {user.posts_count}  点赞数: {user.total_likes}  媒体数: {user.media_count}",
        f"定位: {user.location or '（无）'}  链接: {user.link or '（无）'}  出生年份: {user.birth_year or '（无）'}",
        f"专业领域: {user.profession or '（无）'}  付费订阅: {user.is_subscribed}  私密账号: {user.is_private}",
        "",
        "## 规则预判候选标签",
        "、".join(rule_labels) if rule_labels else "（无命中）",
        "",
    ]

    if analysis_input.tweets:
        lines.append("## 推文样本（被回复或转发帖子内容）")
        for i, t in enumerate(analysis_input.tweets[:20], 1):
            lines.append(f"{i}. {t.text[:max_len]}")
        lines.append("")

    if analysis_input.replies:
        lines.append("## 回复样本（被回复或转发帖子内容）")
        for i, r in enumerate(analysis_input.replies[:20], 1):
            lines.append(f"{i}. {r.text[:max_len]}")
        lines.append("")

    if analysis_input.following:
        lines.append("## 正在关注的账号（前50条）")
        accounts = [f.account for f in analysis_input.following[:50]]
        lines.append("、".join(accounts))
        lines.append("")

    return "\n".join(lines)


def classify_user(
    analysis_input: UserAnalysisInput,
    rule_labels: list[str],
) -> dict:
    """
    调用 LLM 对用户做综合标签判定和画像生成。

    Returns:
        dict with keys: labels, reasoning_brief, profile_summary
    """
    cfg = get_config()
    model_cfg = cfg.get("model", {})
    label_order: list[str] = cfg.get("labels", {}).get("order", [])

    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        labels="\n".join(f"- {l}" for l in label_order)
    )
    user_prompt = _build_user_prompt(analysis_input, rule_labels)

    client = _get_client()
    resp = client.chat.completions.create(
        model=model_cfg.get("model_name", "qwen-plus"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=float(model_cfg.get("temperature", 0.1)),
        max_tokens=4096,
    )
    content = (resp.choices[0].message.content or "").strip()
    logger.debug("用户 %s 模型原始输出: %s", analysis_input.user.account, content[:200])

    data = parse_json_safe(content)
    if not data:
        logger.error("用户 %s 模型输出 JSON 解析失败，原始输出前500字: %s", analysis_input.user.account, content[:500])
        return {"labels": [], "reasoning_brief": "JSON解析失败", "profile_summary": ""}

    return {
        "labels": data.get("labels") or [],
        "reasoning_brief": data.get("reasoning_brief") or "",
        "profile_summary": data.get("profile_summary") or "",
    }
