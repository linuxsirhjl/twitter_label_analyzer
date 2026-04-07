"""users_following 表的读取操作。"""
from __future__ import annotations

from app.db import fetch_all
from app.models import FollowingRecord


def get_following_by_user(
    account_id: str,
    account: str,
) -> list[FollowingRecord]:
    """读取用户正在关注的账号列表。"""
    if account_id:
        sql = (
            "SELECT `正在关注用户账号` AS account, `正在关注用户昵称` AS nickname, "
            "`正在关注用户简介` AS bio FROM `users_following` WHERE `账号ID` = %s"
        )
        rows = fetch_all(sql, (account_id,))
    else:
        sql = (
            "SELECT `正在关注用户账号` AS account, `正在关注用户昵称` AS nickname, "
            "`正在关注用户简介` AS bio FROM `users_following` WHERE `账号` = %s"
        )
        rows = fetch_all(sql, (account,))
    return [
        FollowingRecord(
            account=r.get("account") or "",
            nickname=r.get("nickname") or "",
            bio=r.get("bio") or "",
        )
        for r in rows
    ]
