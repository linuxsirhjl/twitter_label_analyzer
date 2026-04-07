#!/usr/bin/env python3
"""
探查 MySQL 数据库结构：列出所有表及字段信息，并导出为 JSON。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="探查 MySQL 表和字段结构")
    parser.add_argument("--host", default="192.168.51.243", help="MySQL 主机")
    parser.add_argument("--port", type=int, default=3308, help="MySQL 端口")
    parser.add_argument("--user", default="root", help="MySQL 用户名")
    parser.add_argument("--password", default="sdwj.NET", help="MySQL 密码")
    parser.add_argument("--database", default="social_media_crawler", help="数据库名")
    parser.add_argument(
        "--output",
        default="data/mysql_schema_social_media_crawler.json",
        help="输出 JSON 文件路径",
    )
    parser.add_argument(
        "--include-row-count",
        action="store_true",
        help="是否统计每张表的行数（可能较慢）",
    )
    return parser.parse_args()


def fetch_tables(conn: pymysql.Connection, database: str) -> list[dict[str, Any]]:
    sql = """
        SELECT
            TABLE_NAME,
            TABLE_TYPE,
            ENGINE,
            TABLE_ROWS,
            TABLE_COMMENT,
            CREATE_TIME,
            UPDATE_TIME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME
    """
    with conn.cursor() as cur:
        cur.execute(sql, (database,))
        return list(cur.fetchall())


def fetch_columns(conn: pymysql.Connection, database: str) -> list[dict[str, Any]]:
    sql = """
        SELECT
            TABLE_NAME,
            COLUMN_NAME,
            ORDINAL_POSITION,
            COLUMN_TYPE,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COLUMN_KEY,
            EXTRA,
            CHARACTER_SET_NAME,
            COLLATION_NAME,
            COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    with conn.cursor() as cur:
        cur.execute(sql, (database,))
        return list(cur.fetchall())


def fetch_indexes(conn: pymysql.Connection, database: str) -> list[dict[str, Any]]:
    sql = """
        SELECT
            TABLE_NAME,
            INDEX_NAME,
            NON_UNIQUE,
            SEQ_IN_INDEX,
            COLUMN_NAME,
            INDEX_TYPE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
    """
    with conn.cursor() as cur:
        cur.execute(sql, (database,))
        return list(cur.fetchall())


def attach_row_count(conn: pymysql.Connection, tables: list[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        for tbl in tables:
            table_name = tbl["TABLE_NAME"]
            cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
            row = cur.fetchone() or {}
            tbl["EXACT_ROWS"] = row.get("cnt", 0)


def build_schema(
    tables: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    indexes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    table_map: dict[str, dict[str, Any]] = {}
    for t in tables:
        name = t["TABLE_NAME"]
        table_map[name] = {
            "table_name": name,
            "table_type": t["TABLE_TYPE"],
            "engine": t["ENGINE"],
            "estimated_rows": t["TABLE_ROWS"],
            "table_comment": t["TABLE_COMMENT"],
            "create_time": str(t["CREATE_TIME"]) if t["CREATE_TIME"] else None,
            "update_time": str(t["UPDATE_TIME"]) if t["UPDATE_TIME"] else None,
            "exact_rows": t.get("EXACT_ROWS"),
            "columns": [],
            "indexes": [],
        }

    for c in columns:
        table_map[c["TABLE_NAME"]]["columns"].append(
            {
                "name": c["COLUMN_NAME"],
                "position": c["ORDINAL_POSITION"],
                "column_type": c["COLUMN_TYPE"],
                "data_type": c["DATA_TYPE"],
                "nullable": c["IS_NULLABLE"] == "YES",
                "default": c["COLUMN_DEFAULT"],
                "key": c["COLUMN_KEY"],
                "extra": c["EXTRA"],
                "charset": c["CHARACTER_SET_NAME"],
                "collation": c["COLLATION_NAME"],
                "comment": c["COLUMN_COMMENT"],
            }
        )

    for i in indexes:
        table_map[i["TABLE_NAME"]]["indexes"].append(
            {
                "index_name": i["INDEX_NAME"],
                "non_unique": bool(i["NON_UNIQUE"]),
                "seq_in_index": i["SEQ_IN_INDEX"],
                "column_name": i["COLUMN_NAME"],
                "index_type": i["INDEX_TYPE"],
            }
        )

    return [table_map[name] for name in sorted(table_map)]


def print_summary(schema: list[dict[str, Any]]) -> None:
    print(f"共发现 {len(schema)} 张表：")
    for table in schema:
        col_count = len(table["columns"])
        row_info = (
            f", 行数(精确)={table['exact_rows']}"
            if table.get("exact_rows") is not None
            else f", 行数(估算)={table.get('estimated_rows')}"
        )
        print(f"- {table['table_name']} (字段={col_count}{row_info})")


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = pymysql.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )
    except pymysql.err.OperationalError as e:
        code = e.args[0] if e.args else None
        msg = e.args[1] if len(e.args) > 1 else str(e)
        print(f"MySQL 连接失败: {e}")
        if code == 1045:
            print("\n检测到 1045（账号/主机权限被拒绝）。")
            print("当前请求是数据库把你识别为: root@'172.17.0.1'。")
            print("请让数据库管理员在 MySQL 里执行以下授权（示例）：")
            print(
                f"""
CREATE USER IF NOT EXISTS 'root'@'172.17.0.1' IDENTIFIED BY '{args.password}';
GRANT ALL PRIVILEGES ON `{args.database}`.* TO 'root'@'172.17.0.1';
FLUSH PRIVILEGES;
"""
            )
            print("或更建议创建独立只读账号（推荐）：")
            print(
                f"""
CREATE USER IF NOT EXISTS 'crawler_ro'@'%' IDENTIFIED BY '请替换为强密码';
GRANT SELECT ON `{args.database}`.* TO 'crawler_ro'@'%';
FLUSH PRIVILEGES;
"""
            )
            print("然后改用 --user crawler_ro --password 对应密码 连接。")
        elif code == 2003:
            print("\n检测到 2003（无法连接到 MySQL 服务）。请检查 IP/端口、防火墙和 Docker 端口映射。")
        elif code == 1049:
            print(f"\n检测到 1049（数据库不存在）：{args.database}")
        else:
            print(f"\n错误码: {code}, 详情: {msg}")
        sys.exit(1)
    try:
        tables = fetch_tables(conn, args.database)
        columns = fetch_columns(conn, args.database)
        indexes = fetch_indexes(conn, args.database)
        if args.include_row_count:
            attach_row_count(conn, tables)

        schema = build_schema(tables, columns, indexes)
        payload = {
            "database": args.database,
            "host": args.host,
            "port": args.port,
            "table_count": len(schema),
            "tables": schema,
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print_summary(schema)
        print(f"\n结构明细已写入: {output_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
