"""数据库连接与 SQL 执行封装。"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

import pymysql
import pymysql.cursors
from dbutils.pooled_db import PooledDB

from app.settings import get_config

logger = logging.getLogger(__name__)

# 全局连接池
_pool: PooledDB | None = None


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


def _init_pool() -> PooledDB:
    """初始化数据库连接池。"""
    params = _get_conn_params()
    return PooledDB(
        creator=pymysql,
        maxconnections=20,  # 最大连接数
        mincached=2,        # 启动时创建的空闲连接数
        maxcached=10,       # 连接池中最多闲置的连接数
        blocking=True,      # 连接池满时是否阻塞等待
        ping=1,             # 检查连接有效性（0=不检查，1=默认检查，2=使用时检查，4=事务开始时检查，7=总是检查）
        **params
    )


def get_connection() -> pymysql.connections.Connection:
    """从连接池获取一个数据库连接。"""
    global _pool
    if _pool is None:
        _pool = _init_pool()
        logger.info("数据库连接池已初始化")
    return _pool.connection()


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
