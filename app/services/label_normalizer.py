"""标签归一化：去重、过滤非法标签、固定顺序、处理互斥。"""
from __future__ import annotations

from app.constants import LABEL_ORDER, SAFE_LABEL
from app.settings import get_config


def normalize_labels(raw_labels: list[str]) -> list[str]:
    """
    归一化标签列表：
    - 过滤非法标签
    - 去重
    - 处理"无敏感倾向"互斥
    - 按固定顺序输出
    """
    cfg = get_config()
    valid_set = set(cfg.get("labels", {}).get("order", LABEL_ORDER))
    order = cfg.get("labels", {}).get("order", LABEL_ORDER)

    filtered = [l for l in raw_labels if l in valid_set]
    unique = list(dict.fromkeys(filtered))  # 去重保序

    sensitive = [l for l in unique if l != SAFE_LABEL]
    if sensitive:
        # 有敏感标签，不能包含"无敏感倾向"
        result = sensitive
    elif not unique:
        result = [SAFE_LABEL]
    else:
        result = [SAFE_LABEL]

    # 按固定顺序排列
    return [l for l in order if l in result]
