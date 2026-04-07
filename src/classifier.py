"""
多标签分类模块：对中文推文打标签。
推荐用大模型：语义理解好、多标签输出灵活、无需标注数据训练。
"""
from __future__ import annotations

import json
import os
import re
from typing import List

from openai import OpenAI

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

DEFAULT_LABELS = [
    "可能涉及恐怖袭击",
    "可能涉及对国家领导人不利发言",
    "可能涉及反动言论",
]


def _get_compatible_openai_client(*, api_key: str | None = None, base_url: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> OpenAI:
    """
    OpenAI 兼容客户端：
    - OpenAI：api_key=OPENAI_API_KEY，base_url=None
    - 阿里 DashScope（北京区兼容模式）：api_key=DASHSCOPE_API_KEY，base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
    - 使用 connect 超时，避免连接阶段长时间无响应。
    """
    import httpx
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


def classify_with_openai(
    text: str,
    labels: List[str],
    *,
    model: str = "qwen3.5-plus",
    base_url: str | None = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    timeout: float = DEFAULT_TIMEOUT,
) -> List[str]:
    """用大模型对一条推文做多标签分类，返回命中的标签列表（可为空）。"""
    client = _get_compatible_openai_client(base_url=base_url, timeout=timeout)
    # 避免译文/噪声过长拖垮分类；正文取前 4000 字足够
    body = (text or "")[:4000]
    if "Thinking process" in body or len(body) > 2000 and body.count("Analyze") > 2:
        paragraphs = [p for p in body.split("\n\n") if len(re.findall(r"[\u4e00-\u9fff]", p)) > 20]
        body = paragraphs[-1][:4000] if paragraphs else body[:1500]
    has_safe = "无敏感内容" in labels
    risk_only = [l for l in labels if l != "无敏感内容"]
    risk_str = "\n".join(f"- {l}" for l in risk_only)
    if has_safe:
        extra_rule = """
规则：
- 若推文命中上述任一「风险类」标签，只输出这些风险标签，不要输出「无敏感内容」。
- 若推文明显不属于任何风险类（日常、游戏、技术等正常内容），则只输出：{"labels": ["无敏感内容"]}。
- 「无敏感内容」不得与任何风险类标签出现在同一结果里。"""
        labels_block = f"风险类标签：\n{risk_str}\n\n其它：\n- 无敏感内容"
    else:
        extra_rule = "\n若没有任何命中，输出：{\"labels\": []}"
        labels_block = labels_str
    prompt = f"""你是一个内容安全审核助手。请根据预定义标签判断推文。
只输出 JSON，不要其它文字。

{labels_block}
{extra_rule}

推文内容：
{body}

请严格输出（示例格式）：
{{"labels": ["标签1"]}}
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    content = (resp.choices[0].message.content or "").strip()
    # 兼容可能带 markdown 代码块
    if "```" in content:
        content = re.sub(r"```\w*\n?", "", content)
    content = content.strip()
    try:
        data = json.loads(content)
        chosen = data.get("labels") or []
        chosen = [c for c in chosen if c in labels]
        if has_safe:
            risk_chosen = [c for c in chosen if c != "无敏感内容"]
            if risk_chosen:
                return risk_chosen
            if "无敏感内容" in chosen or not chosen:
                return ["无敏感内容"] if "无敏感内容" in labels else []
        return chosen
    except Exception:
        return ["无敏感内容"] if has_safe and "无敏感内容" in labels else []


def classify(
    text: str,
    labels: List[str] | None = None,
    *,
    provider: str = "dashscope",
    model: str = "qwen3.5-plus",
    base_url: str | None = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    timeout: float = DEFAULT_TIMEOUT,
) -> List[str]:
    """统一入口：对中文推文进行多标签分类。"""
    labels = labels or DEFAULT_LABELS
    if provider in ("dashscope", "openai-compatible", "openai"):
        return classify_with_openai(text, labels=labels, model=model, base_url=base_url, timeout=timeout)
    return classify_with_openai(text, labels=labels, model=model, base_url=base_url, timeout=timeout)
