"""key_focus_user 表的写入操作。"""
from __future__ import annotations

import logging

from app.db import transaction

logger = logging.getLogger(__name__)


def upsert_key_focus_users(users: list[dict]) -> int:
    """
    将涉政用户批量写入 key_focus_user 表（存在则更新，不存在则插入）。

    Args:
        users: list of dict with keys: account, account_id, user_category, user_profile_summary

    Returns:
        写入成功条数
    """
    if not users:
        return 0

    sql = """
        INSERT INTO key_focus_user
            (account, account_id, user_category, user_profile_summary, profile_url)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            account_id = VALUES(account_id),
            user_category = VALUES(user_category),
            user_profile_summary = VALUES(user_profile_summary),
            profile_url = VALUES(profile_url),
            updated_at = CURRENT_TIMESTAMP
    """
    rows = [
        (
            u["account"],
            u.get("account_id") or "",
            u.get("user_category") or "",
            u.get("user_profile_summary") or "",
            f"https://x.com/{u['account']}",
        )
        for u in users
    ]

    with transaction() as cursor:
        cursor.executemany(sql, rows)

    logger.info("key_focus_user 写入/更新 %d 条", len(rows))
    return len(rows)
