"""users_replies 表的读取操作。"""
from __future__ import annotations

from app.db import fetch_all
from app.models import ReplyRecord


def get_replies_by_user(
    account_id: str,
    account: str,
    limit: int = 20,
) -> list[ReplyRecord]:
    """读取用户最近 N 条非空回复（被回复或转发帖子内容）。"""
    if account_id:
        sql = (
            "SELECT `被回复或转发帖子内容` AS text FROM `users_replies` "
            "WHERE `账号ID` = %s AND `被回复或转发帖子内容` IS NOT NULL "
            "AND `被回复或转发帖子内容` != '' "
            "ORDER BY `id` DESC LIMIT %s"
        )
        rows = fetch_all(sql, (account_id, limit))
    else:
        sql = (
            "SELECT `被回复或转发帖子内容` AS text FROM `users_replies` "
            "WHERE `账号` = %s AND `被回复或转发帖子内容` IS NOT NULL "
            "AND `被回复或转发帖子内容` != '' "
            "ORDER BY `id` DESC LIMIT %s"
        )
        rows = fetch_all(sql, (account, limit))
    return [ReplyRecord(text=r["text"]) for r in rows]
