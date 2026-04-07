"""JSON 解析工具，支持容错修复。"""
from __future__ import annotations

import json
import re


def _extract_json_object(s: str) -> str:
    """用括号配对从文本中提取第一个完整 JSON 对象。"""
    if not s:
        return ""
    # 去除 markdown 代码块
    s = re.sub(r"```\w*\n?", "", s).strip()
    # 跳过 </think> 之前的内容
    if "</think>" in s:
        s = s.split("</think>", 1)[-1].strip()
    start = s.find("{")
    if start == -1:
        return ""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return ""


def parse_json_safe(text: str) -> dict | None:
    """尝试解析 JSON，支持思考过程包裹、markdown 代码块等情况。"""
    if not text:
        return None
    extracted = _extract_json_object(text)
    if not extracted:
        return None
    try:
        return json.loads(extracted)
    except json.JSONDecodeError:
        return None
