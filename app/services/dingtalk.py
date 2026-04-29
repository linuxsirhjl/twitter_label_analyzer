"""钉钉机器人推送服务。"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import requests

from app.settings import get_config

logger = logging.getLogger(__name__)


def _build_text(
    status: str,
    start_time: datetime,
    end_time: datetime,
    total_users: int,
    success: int,
    failed: int,
    political_users: list[dict],
    error_summary: str,
    secret_keyword: str,
    max_display: int,
) -> str:
    duration_sec = int((end_time - start_time).total_seconds())
    duration_str = f"{duration_sec // 60}分{duration_sec % 60}秒"

    lines = [
        f"### {secret_keyword} - 用户分析任务完成",
        "",
        f"- 状态：{'✅ 成功' if status == 'success' else '❌ 失败'}",
        f"- 开始时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 结束时间：{end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总耗时：{duration_str}",
        f"- 分析用户数：{total_users}（成功 {success}，失败 {failed}）",
    ]

    if error_summary:
        lines.append(f"- 错误摘要：{error_summary[:200]}")

    total_political = len(political_users)
    lines += ["", f"#### 涉政用户（共 {total_political} 人）"]

    if total_political == 0:
        lines.append("> 本次未发现涉政用户")
    else:
        shown = political_users[:max_display]
        for u in shown:
            account = u["account"]
            link = f"https://x.com/{account}"
            profile = u.get("user_profile_summary") or u.get("profile_summary") or "（暂无画像）"
            lines.append(f"> @{account}：{link}  ")
            lines.append(f"> 画像：{profile}")
            lines.append("")
        if total_political > max_display:
            lines.append(f"> ...共 {total_political} 人")

    return "\n".join(lines)


def send_task_report(
    *,
    status: str,
    start_time: datetime,
    end_time: datetime,
    total_users: int,
    success: int,
    failed: int,
    political_users: list[dict],
    error_summary: str = "",
) -> None:
    """发送任务完成报告到钉钉，失败只记日志不抛异常。"""
    cfg = get_config()
    dt_cfg = cfg.get("dingtalk", {})
    if not dt_cfg.get("enabled", False):
        return

    webhook: str = dt_cfg.get("webhook", "") or os.environ.get("DINGTALK_WEBHOOK", "")
    if not webhook:
        logger.warning("钉钉 webhook 未配置，跳过推送")
        return

    secret_keyword: str = dt_cfg.get("secret_keyword", "分析任务")
    max_display: int = int(dt_cfg.get("max_users_display", 20))
    at_mobiles: list = dt_cfg.get("at_mobiles") or []
    at_user_ids: list = dt_cfg.get("at_user_ids") or []
    is_at_all: bool = bool(dt_cfg.get("is_at_all", False))

    text = _build_text(
        status=status,
        start_time=start_time,
        end_time=end_time,
        total_users=total_users,
        success=success,
        failed=failed,
        political_users=political_users,
        error_summary=error_summary,
        secret_keyword=secret_keyword,
        max_display=max_display,
    )

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": "用户分析任务完成", "text": text},
        "at": {
            "atMobiles": at_mobiles,
            "atUserIds": at_user_ids,
            "isAtAll": is_at_all,
        },
    }

    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("errcode") != 0:
            logger.error("钉钉推送失败: %s", result)
        else:
            logger.info("钉钉推送成功")
    except Exception as e:
        logger.error("钉钉推送异常: %s", e)
