"""涉政用户查询。"""
from __future__ import annotations

from app.db import fetch_all


def get_political_users(limit: int = 20) -> list[dict]:
    """查询 user_category 包含"涉政"的用户，返回账号、账号ID、标签、用户画像。"""
    sql = (
        "SELECT `账号`, `账号ID`, `user_category`, `user_profile_summary` "
        "FROM `users_basic_info` "
        "WHERE `user_category` LIKE %s "
        "ORDER BY `id` DESC"
    )
    rows = fetch_all(sql, ("%涉政%",))
    return [
        {
            "account": r.get("账号") or "",
            "account_id": r.get("账号ID") or "",
            "user_category": r.get("user_category") or "",
            "user_profile_summary": r.get("user_profile_summary") or "",
        }
        for r in rows
    ]
