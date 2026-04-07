"""
主流程：读入推文 → 非中文则翻译 → 多标签分类 → 输出 (推文, 标签列表)。
支持输入：JSON、JSONL、Excel(.xlsx)、CSV；Excel 默认 W 列，CSV 默认按列名「帖子」或 text/content。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List

import pandas as pd
import yaml
from tqdm import tqdm

from .classifier import classify
from .translator import translate


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


def check_api_connection(config_path: str | Path = "config.yaml", timeout: float = 25.0) -> tuple[bool, str]:
    """
    启动前检测 API 是否可达。返回 (成功, 消息)。
    若 25 秒内无响应会超时并返回失败，避免正式跑时长时间无响应。
    """
    config = load_config(config_path)
    cfg_c = config.get("classifier") or {}
    provider = cfg_c.get("provider") or "dashscope"
    base_url = cfg_c.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = cfg_c.get("model") or "qwen3.5-plus"
    labels = config.get("labels") or ["无敏感内容"]
    try:
        # 本地/内网服务：优先用 /health 探活，避免首 token 很慢导致“误报超时”
        if _is_local_base_url(base_url):
            import httpx

            # base_url 常见是 http://host:5000/v1 → health 在根路径
            root = str(base_url)
            if root.endswith("/v1"):
                root = root[:-3]
            root = root.rstrip("/")
            health_url = f"{root}/health"
            r = httpx.get(health_url, timeout=min(float(timeout), 10.0))
            if r.status_code == 200:
                return True, "本地模型服务健康，开始处理。"
            return False, f"本地模型服务探活失败：HTTP {r.status_code}（{health_url}）"

        classify("你好", labels=labels, provider=provider, model=model, base_url=base_url, timeout=timeout)
        return True, "API 连通正常，开始处理。"
    except Exception as e:
        return False, f"API 检测失败（{int(timeout)} 秒内无有效响应）：{type(e).__name__}: {e}"


def load_config(config_path: str | Path = "config.yaml") -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        path = Path("config.example.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run(
    tweets: List[Dict[str, Any]],
    *,
    config: Dict[str, Any] | None = None,
    config_path: str | Path = "config.yaml",
    on_result: Callable[[Dict[str, Any]], None] | None = None,
) -> List[Dict[str, Any]]:
    """对每条推文：翻译（如需）→ 分类，返回 [{raw, text_zh, labels}, ...]。on_result 若提供则每条写完即调用，用于增量写盘。"""
    if config is None:
        config = load_config(config_path)
    cfg_t = config.get("translator") or {}
    cfg_c = config.get("classifier") or {}
    labels = config.get("labels") or [
        "可能涉及恐怖袭击",
        "可能涉及对国家领导人不利发言",
        "可能涉及反动言论",
    ]
    provider_t = cfg_t.get("provider") or "dashscope"
    provider_c = cfg_c.get("provider") or "dashscope"
    model_t = cfg_t.get("model") or "qwen3.5-plus"
    model_c = cfg_c.get("model") or "qwen3.5-plus"
    base_url_t = cfg_t.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    base_url_c = cfg_c.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    timeout = float(config.get("api_timeout", 120))

    n = len(tweets)
    print(f"共 {n} 条推文，开始处理（每条会调用 1～2 次 API，首条可能需 1～2 分钟，超时 {int(timeout)} 秒）…")
    results = []
    pbar = tqdm(tweets, desc="处理推文", total=n)
    for idx, item in enumerate(pbar):
        raw = item.get("text") or item.get("content") or str(item)
        raw_preview = (raw[:80] + "…") if isinstance(raw, str) and len(raw) > 80 else raw
        if idx == 0:
            print(f"第 1 条示例（截断预览）：{raw_preview}")

        err: str | None = None
        text_zh = raw
        tag_list: List[str] = []
        try:
            try:
                pbar.set_postfix_str("翻译中")
                text_zh = translate(
                    raw,
                    provider=provider_t,
                    model=model_t,
                    base_url=base_url_t,
                    timeout=timeout,
                )
            except Exception as e:
                text_zh = raw
                err = f"translate_error: {type(e).__name__}: {e}"

            try:
                pbar.set_postfix_str("分类中")
                tag_list = classify(
                    text_zh,
                    labels=labels,
                    provider=provider_c,
                    model=model_c,
                    base_url=base_url_c,
                    timeout=timeout,
                )
            except Exception as e:
                tag_list = []
                err2 = f"classify_error: {type(e).__name__}: {e}"
                err = f"{err}; {err2}" if err else err2
        except Exception as e:
            err = f"unexpected: {type(e).__name__}: {e}"

        pbar.set_postfix_str("")
        one = {
            "raw": raw,
            "text_zh": text_zh,
            "labels": tag_list,
            **({"error": err} if err else {}),
        }
        results.append(one)
        if on_result is not None:
            on_result(one)
    return results


def _load_tweets_from_excel(path: Path, text_column: str = "W") -> List[Dict[str, Any]]:
    """从 Excel 读取推文。默认使用 W 列（第 23 列）。"""
    df = pd.read_excel(path, engine="openpyxl")
    # W 列：列字母 W = 第 23 列，0-based 索引为 22
    col_idx = ord(text_column.upper()) - ord("A")  # W -> 22
    if col_idx >= df.shape[1]:
        raise ValueError(f"Excel 列 {text_column} 不存在，当前共 {df.shape[1]} 列")
    col = df.iloc[:, col_idx]
    tweets = []
    for i, val in enumerate(col):
        if pd.isna(val):
            continue
        s = str(val).strip()
        if not s:
            continue
        tweets.append({"text": s, "_excel_row": i + 2})  # +2: 1-based + 表头
    return tweets


# CSV 推文列名候选（按优先级尝试）
_DEFAULT_CSV_TEXT_COLUMNS = ["帖子", "text", "content", "推文", "内容"]


def _load_tweets_from_csv(
    path: Path,
    text_column: str | None = None,
    encoding: str = "utf-8",
) -> List[Dict[str, Any]]:
    """从 CSV 读取推文。text_column 为列名，缺省时自动尝试常见列名或第一列。"""
    try:
        df = pd.read_csv(path, encoding=encoding)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="gbk")
    if df.shape[1] == 0:
        return []
    if text_column is not None:
        if text_column not in df.columns:
            raise ValueError(f"CSV 中不存在列「{text_column}」，当前列：{list(df.columns)}")
        col = df[text_column]
    else:
        for name in _DEFAULT_CSV_TEXT_COLUMNS:
            if name in df.columns:
                col = df[name]
                break
        else:
            col = df.iloc[:, 0]
    tweets = []
    for val in col:
        if pd.isna(val):
            continue
        s = str(val).strip()
        if not s:
            continue
        tweets.append({"text": s})
    return tweets


def run_from_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    config_path: str | Path = "config.yaml",
    excel_text_column: str = "W",
    csv_text_column: str | None = None,
    resume: bool = False,
) -> None:
    """从 JSON/JSONL/Excel/CSV 文件读推文，运行 pipeline，写回 JSON 结果。支持 --resume 从上次中断处继续（按 .jsonl 行数跳过）。"""
    path = Path(input_path)
    tweets = []
    if path.suffix.lower() == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tweets.append(json.loads(line))
    elif path.suffix.lower() == ".xlsx":
        tweets = _load_tweets_from_excel(path, text_column=excel_text_column)
        if not tweets:
            print("Excel 中未找到非空推文，请确认推文所在列（默认 W 列）")
            return
    elif path.suffix.lower() == ".csv":
        tweets = _load_tweets_from_csv(path, text_column=csv_text_column)
        if not tweets:
            print("CSV 中未找到非空推文，请用 --text-column 指定推文列名")
            return
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            tweets = data
        else:
            tweets = data.get("tweets", data.get("items", [data]))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # 增量写用 .jsonl；若用户指定 .json 则先写 result.jsonl，最后再生成 result.json
    use_jsonl = out.suffix.lower() == ".json"
    jsonl_path = out.with_suffix(".jsonl") if use_jsonl else out
    skip = 0
    if resume and jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            skip = sum(1 for _ in f)
        if skip > 0:
            tweets = tweets[skip:]
            print(f"已恢复：跳过前 {skip} 条，剩余 {len(tweets)} 条")
    mode = "a" if resume and jsonl_path.exists() and skip > 0 else "w"
    with open(jsonl_path, mode, encoding="utf-8") as f:

        def on_result(one: Dict[str, Any]) -> None:
            f.write(json.dumps(one, ensure_ascii=False) + "\n")
            f.flush()

        results = run(tweets, config_path=config_path, on_result=on_result)

    if use_jsonl:
        # 最终 .json 从 .jsonl 全量读出（含 resume 时之前已写的行）
        with open(jsonl_path, "r", encoding="utf-8") as f:
            existing = [json.loads(line) for line in f if line.strip()]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"已写入 {len(existing)} 条结果到 {out}（增量备份 {jsonl_path}）")
    else:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"已写入 {len(results)} 条结果到 {out}")
