"""语言检测工具。"""
from __future__ import annotations

import re


def is_mainly_chinese(text: str, ratio: float = 0.3) -> bool:
    """判断文本是否主要为中文（中文字符占比超过 ratio）。"""
    if not text or not text.strip():
        return True
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    return chinese / max(len(text), 1) >= ratio
