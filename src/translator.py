"""
翻译模块：将非中文推文翻译成中文。
建议：多语言场景用大模型或专用翻译 API（如 DeepL、百度），质量稳定、支持语种多。
"""
from __future__ import annotations

import os
import re

# 单次 API 请求超时（秒），避免长时间卡在 0%
DEFAULT_TIMEOUT = 120

def _is_local_base_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        import ipaddress

        host = (urlparse(url).hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            ip = ipaddress.ip_address(host)
            return bool(ip.is_private or ip.is_loopback)
        except ValueError:
            return False
    except Exception:
        return False


# 简单判断是否主要为中文（可替换为 langdetect）
def is_mainly_chinese(text: str, ratio: float = 0.3) -> bool:
    if not text or not text.strip():
        return True
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    return chinese / max(len(text), 1) >= ratio


def _get_compatible_openai_client(*, api_key: str | None = None, base_url: str | None = None, timeout: float = DEFAULT_TIMEOUT):
    """
    OpenAI 兼容客户端：
    - OpenAI：api_key=OPENAI_API_KEY，base_url=None
    - 阿里 DashScope（北京区兼容模式）：api_key=DASHSCOPE_API_KEY，base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
    - 使用 connect 超时，避免连接阶段长时间无响应。
    """
    import httpx
    from openai import OpenAI
    api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # 本地/内网 OpenAI 兼容服务通常不校验 key，但 SDK 仍要求有值
        if _is_local_base_url(base_url):
            api_key = "local"
        else:
            raise RuntimeError("缺少 API Key：请设置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY")
    # 默认 timeout，连接单独 15 秒，避免“一直连不上”却等很久
    http_timeout = httpx.Timeout(timeout, connect=15.0)
    return OpenAI(api_key=api_key, base_url=base_url, timeout=http_timeout)


def _clean_translation_output(content: str) -> str:
    """若模型仍输出思考过程，尽量只保留译文段（含中文最多的一行/段）。"""
    if not content or not content.strip():
        return content
    if "Thinking process" not in content and "thinking process" not in content.lower():
        return content.strip()
    # 按段拆开，取「中文占比最高且不太像列表标题」的一段作为译文
    chunks = re.split(r"\n{2,}", content)
    best = ""
    best_score = -1.0
    for c in chunks:
        c = c.strip()
        if not c or len(c) < 8:
            continue
        if re.match(r"^\d+\.\s*\*?\*?Analyze", c, re.I):
            continue
        if c.startswith("```"):
            continue
        zh = len(re.findall(r"[\u4e00-\u9fff]", c))
        score = zh / max(len(c), 1)
        if zh >= 10 and score > best_score:
            best_score = score
            best = c
    if best:
        return best.strip()
    # 退化为取最后一行含中文较多的短句
    for line in reversed(content.split("\n")):
        line = line.strip()
        if len(re.findall(r"[\u4e00-\u9fff]", line)) >= 8:
            return line
    return content.strip()


def translate_with_llm(
    text: str,
    *,
    target_lang: str = "简体中文",
    model: str = "qwen3.5-plus",
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """使用 OpenAI 兼容接口将任意语言翻译成中文（默认适配 Qwen3.5）。"""
    client = _get_compatible_openai_client(base_url=base_url, timeout=timeout)
    system = f"""你是翻译器。任务：把用户给出的原文翻译成{target_lang}。

硬性规则（违反任意一条视为错误）：
1. 只输出译文本身，一行或一小段均可。
2. 禁止输出思考过程、分析、步骤、英文解释、「Thinking process」、选项对比、Markdown 标题。
3. 禁止输出「译文：」「翻译如下」等前缀，直接以译文开头。
4. 保留原文里的 URL、@用户名、话题标签不翻译或照抄。"""
    user = f"请只翻译下面这句话/段，不要任何其它内容：\n\n{text[:8000]}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=1024,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _clean_translation_output(raw)


def translate(
    text: str,
    *,
    provider: str = "dashscope",
    model: str = "qwen3.5-plus",
    base_url: str | None = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """统一入口：若已是中文则直接返回，否则按 provider 翻译。"""
    if is_mainly_chinese(text):
        return text
    if provider in ("dashscope", "openai-compatible", "openai"):
        return translate_with_llm(text, model=model, base_url=base_url, timeout=timeout)
    if provider == "none":
        return text
    return translate_with_llm(text, model=model, base_url=base_url, timeout=timeout)
