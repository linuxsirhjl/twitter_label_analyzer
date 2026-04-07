"""users_followers 表的读取操作。"""
from __future__ import annotations

from app.db import fetch_all
from app.models import FollowerRecord


def get_followers_by_user(
    account_id: str,
    account: str,
    limit: int = 100,
) -> list[FollowerRecord]:
    """读取关注该用户的账号列表（辅助分析，不作为主判定依据）。"""
    if account_id:
        sql = (
            "SELECT `关注者用户账号` AS account FROM `users_followers` "
            "WHERE `账号ID` = %s LIMIT %s"
        )
        rows = fetch_all(sql, (account_id, limit))
    else:
        sql = (
            "SELECT `关注者用户账号` AS account FROM `users_followers` "
            "WHERE `账号` = %s LIMIT %s"
        )
        rows = fetch_all(sql, (account, limit))
    return [FollowerRecord(account=r.get("account") or "") for r in rows]
