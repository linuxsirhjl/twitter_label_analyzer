"""数据库连接与 SQL 执行封装。"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

import pymysql
import pymysql.cursors

from app.settings import get_config

logger = logging.getLogger(__name__)


def _get_conn_params() -> dict[str, Any]:
    cfg = get_config()
    db = cfg["database"]
    return {
        "host": db["host"],
        "port": int(db.get("port", 3306)),
        "user": db["user"],
        "password": db["password"],
        "database": db["db"],
        "charset": db.get("charset", "utf8mb4"),
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }


def get_connection() -> pymysql.connections.Connection:
    """创建并返回一个新的数据库连接。"""
    params = _get_conn_params()
    return pymysql.connect(**params)


@contextmanager
def transaction() -> Generator[pymysql.cursors.DictCursor, None, None]:
    """提供一个带事务的游标上下文管理器，成功提交，失败回滚。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """执行查询并返回所有行。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """执行查询并返回第一行。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()
    finally:
        conn.close()
