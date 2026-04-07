"""规则预判引擎：基于关注名单和关键词做初筛。"""
from __future__ import annotations

import logging
import re

from app.models import UserAnalysisInput
from app.settings import get_config

logger = logging.getLogger(__name__)

# 各标签对应的关键词（辅助规则，不作为唯一判定依据）
_KEYWORD_RULES: dict[str, list[str]] = {
    "涉政": [
        "习近平", "分裂国家", "颠覆政权", "反党", "推翻", "六四", "天安门事件",
        "法轮功", "藏独", "台独", "港独", "新疆独立",
    ],
    "涉恐怖极端": [
        "恐怖袭击", "炸弹", "圣战", "ISIS", "基地组织", "极端主义", "恐怖组织",
    ],
    "涉及传播淫秽赌博": [
        "赌博", "色情", "淫秽", "博彩", "赌场", "黄色网站",
    ],
    "涉及网络犯罪或者网络暴力": [
        "黑客", "网络攻击", "人肉搜索", "网络诈骗", "侵犯隐私", "网络欺凌",
    ],
    "涉及仇恨言论": [
        "种族歧视", "仇恨", "歧视", "煽动暴力",
    ],
}


def run_rule_check(analysis_input: UserAnalysisInput) -> list[str]:
    """
    对用户数据做规则预判，返回候选标签列表。

    规则：
    1. 关注名单命中 → 涉政
    2. 文本关键词命中 → 对应标签候选
    """
    cfg = get_config()
    sensitive_accounts: list[str] = cfg.get("political_sensitive_accounts", [])
    sensitive_set = {a.lower() for a in sensitive_accounts}

    candidate_labels: set[str] = set()

    # 规则1：关注名单
    for f in analysis_input.following:
        if f.account.lower() in sensitive_set:
            candidate_labels.add("涉政")
            logger.info(
                "用户 %s 关注了敏感账号 %s，命中涉政规则",
                analysis_input.user.account,
                f.account,
            )
            break

    # 规则2：文本关键词
    all_texts = (
        [t.text for t in analysis_input.tweets]
        + [r.text for r in analysis_input.replies]
        + [analysis_input.user.bio]
    )
    combined = " ".join(all_texts)
    for label, keywords in _KEYWORD_RULES.items():
        for kw in keywords:
            if kw in combined:
                candidate_labels.add(label)
                logger.info("用户 %s 文本命中关键词 [%s]，候选标签: %s", analysis_input.user.account, kw, label)
                break

    return list(candidate_labels)
