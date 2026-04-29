#!/usr/bin/env python3
"""
用户风险分析系统入口。

用法：
  python main.py                          # 分析所有用户
  python main.py --only-empty             # 只分析未填写 category 的用户
  python main.py --batch-size 50          # 指定批次大小
  python main.py --config config.yaml     # 指定配置文件
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from dotenv import load_dotenv

from app.settings import get_config, reload_config
from app.utils.logger import setup_logging

load_dotenv()


def _send_batch_notification(batch_num: int, batch_size: int, batch_time: float, avg_time: float) -> None:
    """发送批次完成通知到钉钉"""
    try:
        from app.services.dingtalk import send_task_report

        # 构造批次报告
        end_time = datetime.now()
        start_time = datetime.fromtimestamp(end_time.timestamp() - batch_time)

        message = f"批次 #{batch_num} 完成分析"

        send_task_report(
            status="success",
            start_time=start_time,
            end_time=end_time,
            total_users=batch_size,
            success=batch_size,
            failed=0,
            political_users=[],
            error_summary=f"批次耗时: {batch_time:.1f}秒, 平均每用户: {avg_time:.1f}秒"
        )
    except Exception as e:
        logging.getLogger(__name__).warning(f"发送批次通知失败: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="社交媒体用户风险分析系统")
    parser.add_argument("--config", "-c", default="config.yaml", help="配置文件路径")
    parser.add_argument("--only-empty", action="store_true", help="只处理 user_category 为空的用户")
    parser.add_argument("--only-empty-profile", action="store_true", help="只处理 user_profile_summary 为空的用户")
    parser.add_argument("--batch-size", type=int, default=None, help="每批处理用户数（覆盖配置文件）")
    parser.add_argument("--workers", type=int, default=4, help="并发线程数（默认4）")
    parser.add_argument("--debug", action="store_true", help="开启 DEBUG 日志")
    args = parser.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)
    logger = logging.getLogger(__name__)

    cfg = reload_config(args.config)
    analysis_cfg = cfg.get("analysis", {})
    batch_size = args.batch_size or int(analysis_cfg.get("batch_size", 100))
    only_empty_category = args.only_empty or bool(analysis_cfg.get("update_only_empty_category", False))
    only_empty_profile = args.only_empty_profile or bool(analysis_cfg.get("update_only_empty_profile", False))

    from app.repositories.user_repository import get_users_batch
    from app.services.user_analysis_service import analyze_user

    offset = 0
    total_ok = 0
    total_fail = 0
    batch_count = 0
    batch_start_time = time.time()
    batch_user_times = []

    logger.info("开始批量分析，batch_size=%d workers=%d only_empty_category=%s", batch_size, args.workers, only_empty_category)

    def process_user(user):
        user_start = time.time()
        try:
            result = analyze_user(user)
            user_elapsed = time.time() - user_start
            logger.info("✓ 用户 %s [id=%d] 标签=%s", result.account, result.user_id, result.labels)
            return True, user_elapsed
        except Exception as e:
            user_elapsed = time.time() - user_start
            logger.error("✗ 用户 %s [id=%d] 分析失败: %s", user.account, user.id, e, exc_info=True)
            return False, user_elapsed

    while True:
        users = get_users_batch(
            offset,
            batch_size,
            only_empty_category=only_empty_category,
            only_empty_profile=only_empty_profile,
        )
        if not users:
            break

        logger.info("处理第 %d-%d 条用户", offset + 1, offset + len(users))

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process_user, u): u for u in users}
            for future in as_completed(futures):
                success, elapsed = future.result()
                batch_user_times.append(elapsed)
                if success:
                    total_ok += 1
                else:
                    total_fail += 1

        offset += len(users)

        # 每1000个用户统计一次
        if total_ok + total_fail >= (batch_count + 1) * 1000:
            batch_count += 1
            batch_elapsed = time.time() - batch_start_time
            avg_time = sum(batch_user_times) / len(batch_user_times) if batch_user_times else 0

            logger.info(
                "=" * 60 + "\n"
                f"批次 #{batch_count} 完成: 已处理 {batch_count * 1000} 个用户\n"
                f"批次耗时: {batch_elapsed:.1f}秒\n"
                f"平均每用户: {avg_time:.1f}秒\n"
                + "=" * 60
            )

            # 推送到钉钉
            _send_batch_notification(batch_count, 1000, batch_elapsed, avg_time)

            # 重置批次计时器
            batch_start_time = time.time()
            batch_user_times = []

        if len(users) < batch_size:
            break

    logger.info("分析完成：成功 %d 条，失败 %d 条", total_ok, total_fail)


if __name__ == "__main__":
    main()
