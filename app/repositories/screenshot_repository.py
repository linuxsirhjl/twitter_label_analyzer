"""users_replies_and_tweets 表的读取操作，用于获取推文截图路径。"""
from __future__ import annotations

from app.db import fetch_all


def get_screenshot_paths_by_user(
    account_id: str,
    account: str,
) -> dict[str, str]:
    """
    获取用户推文/回复对应的截图路径映射。

    Returns:
        dict: {链接: 截图完整路径}
    """
    # users_replies_and_tweets 表只有 `账号` 列，没有 `账号ID` 列
    sql = (
        "SELECT `链接`, `名称` FROM `users_replies_and_tweets` "
        "WHERE `账号` = %s AND `名称` IS NOT NULL AND `名称` != ''"
    )
    rows = fetch_all(sql, (account,))

    # 拼接完整路径：D:\数据\用户"帖子"和"回复"数据截图\ + 名称
    base_path = r'D:\数据\用户"帖子"和"回复"数据截图'
    result = {}
    for row in rows:
        link = row.get("链接")
        name = row.get("名称")
        if link and name:
            result[link] = f"{base_path}\\{name}"

    return result
