"""users_tweets 表的读取操作。"""
from __future__ import annotations

from app.db import fetch_all
from app.models import TweetRecord


def get_tweets_by_user(
    account_id: str,
    account: str,
    limit: int = 20,
) -> list[TweetRecord]:
    """读取用户最近 N 条非空推文（被回复或转发帖子内容）。"""
    if account_id:
        sql = (
            "SELECT `被回复或转发帖子内容` AS text, `被回复或转发帖子链接` AS link FROM `users_tweets` "
            "WHERE `账号ID` = %s AND `被回复或转发帖子内容` IS NOT NULL "
            "AND `被回复或转发帖子内容` != '' "
            "ORDER BY `id` DESC LIMIT %s"
        )
        rows = fetch_all(sql, (account_id, limit))
    else:
        sql = (
            "SELECT `被回复或转发帖子内容` AS text, `被回复或转发帖子链接` AS link FROM `users_tweets` "
            "WHERE `账号` = %s AND `被回复或转发帖子内容` IS NOT NULL "
            "AND `被回复或转发帖子内容` != '' "
            "ORDER BY `id` DESC LIMIT %s"
        )
        rows = fetch_all(sql, (account, limit))
    return [TweetRecord(text=r["text"], link=r.get("link", "")) for r in rows]
