"""配置加载模块，统一读取 config.yaml 和 .env。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@lru_cache(maxsize=1)
def get_config(config_path: str | None = None) -> dict[str, Any]:
    """加载并缓存配置文件。"""
    path = Path(config_path) if config_path else _CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}
    # 将 .env 中的 DB 密码注入
    db = cfg.setdefault("database", {})
    if not db.get("password"):
        db["password"] = os.environ.get("DB_PASSWORD", "")
    # API Key 从环境变量读取
    model = cfg.setdefault("model", {})
    api_key_env = model.get("api_key_env", "OPENAI_API_KEY")
    model["_api_key"] = os.environ.get(api_key_env, "")
    return cfg


def reload_config(config_path: str | None = None) -> dict[str, Any]:
    """清除缓存并重新加载配置（测试用）。"""
    get_config.cache_clear()
    return get_config(config_path)
