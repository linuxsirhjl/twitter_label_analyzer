"""翻译服务，复用 src/translator.py 的能力，增加配置驱动。"""
from __future__ import annotations

import logging

from app.settings import get_config
from src.translator import translate

logger = logging.getLogger(__name__)


def translate_if_needed(text: str) -> str:
    """根据配置决定是否翻译，若已是中文则直接返回。"""
    cfg = get_config()
    analysis = cfg.get("analysis", {})
    if not analysis.get("enable_translation", True):
        return text
    model_cfg = cfg.get("model", {})
    try:
        return translate(
            text,
            provider=model_cfg.get("provider", "openai_compatible"),
            model=model_cfg.get("model_name", "qwen-plus"),
            base_url=model_cfg.get("base_url"),
            timeout=float(model_cfg.get("timeout", 120)),
        )
    except Exception as e:
        logger.warning("翻译失败，使用原文: %s", e)
        return text
