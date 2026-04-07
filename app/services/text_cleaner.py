"""文本清洗服务。"""
from __future__ import annotations

import re


def clean_text(text: str | None, max_length: int = 1000) -> str:
    """清洗单条文本：去空白、去超长重复字符、截断。"""
    if not text:
        return ""
    text = text.strip()
    # 去除超长重复字符（同一字符连续超过10次）
    text = re.sub(r"(.)\1{10,}", lambda m: m.group(1) * 3, text)
    return text[:max_length]


def deduplicate_texts(texts: list[str]) -> list[str]:
    """去重，保持顺序。"""
    seen: set[str] = set()
    result = []
    for t in texts:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result
