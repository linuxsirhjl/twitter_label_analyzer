"""users_basic_info 表的读取与更新操作。"""
from __future__ import annotations

import logging
from typing import Any

from app.db import fetch_all, transaction
from app.models import BasicUserInfo

logger = logging.getLogger(__name__)

_SELECT_FIELDS = (
    "id, `账号`, `账号ID`, `昵称`, `用户简介`, `总点赞数`, `正在关注数`, `总关注者`, "
    "`帖子数`, `媒体发布数`, `是否设为私密`, `用户提供的定位`, `用户提供的链接`, "
    "`用户提供的出生年份`, `用户提供的专业领域`, `是否付费订阅用户`, "
    "`user_category`, `user_profile_summary`"
)


def get_users_batch(
    offset: int,
    limit: int,
    *,
    only_empty_category: bool = False,
    only_empty_profile: bool = False,
) -> list[BasicUserInfo]:
    """分页读取待分析用户列表。"""
    conditions = []
    if only_empty_category:
        conditions.append("(`user_category` IS NULL OR `user_category` = '')")
    if only_empty_profile:
        conditions.append("(`user_profile_summary` IS NULL OR `user_profile_summary` = '')")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT {_SELECT_FIELDS} FROM `users_basic_info` {where} LIMIT %s OFFSET %s"
    rows = fetch_all(sql, (limit, offset))
    return [BasicUserInfo.from_row(r) for r in rows]


def update_user_analysis(
    user_id: int,
    category: str,
    profile_summary: str,
) -> None:
    """在同一事务中更新 user_category 和 user_profile_summary。"""
    sql = (
        "UPDATE `users_basic_info` "
        "SET `user_category` = %s, `user_profile_summary` = %s "
        "WHERE `id` = %s"
    )
    with transaction() as cursor:
        cursor.execute(sql, (category[:100], profile_summary, user_id))
    logger.info("用户 id=%d 回写成功", user_id)
