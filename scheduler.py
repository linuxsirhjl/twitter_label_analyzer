#!/usr/bin/env python3
"""
定时调度入口。

用法：
  python scheduler.py          # 进入调度模式，每天 18:00 自动触发
  python scheduler.py --now    # 立即执行一次（测试用）
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from app.settings import reload_config
from app.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_running = False


def run_analysis_job() -> None:
    """完整分析流程，执行完后推送钉钉。"""
    global _running
    if _running:
        logger.warning("上一轮任务尚未完成，跳过本次执行")
        return
    _running = True

    cfg = reload_config()
    analysis_cfg = cfg.get("analysis", {})
    batch_size = int(analysis_cfg.get("batch_size", 100))
    only_empty_category = bool(analysis_cfg.get("update_only_empty_category", False))
    only_empty_profile = bool(analysis_cfg.get("update_only_empty_profile", False))
    workers = int(cfg.get("scheduler", {}).get("workers", 4))

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.repositories.user_repository import get_users_batch
    from app.repositories.political_repository import get_political_users
    from app.repositories.key_focus_repository import upsert_key_focus_users
    from app.services.user_analysis_service import analyze_user
    from app.services.dingtalk import send_task_report

    start_time = datetime.now()
    total_ok = 0
    total_fail = 0
    error_summary = ""

    logger.info("定时任务开始执行 %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))

    try:
        offset = 0
        while True:
            users = get_users_batch(
                offset, batch_size,
                only_empty_category=only_empty_category,
                only_empty_profile=only_empty_profile,
            )
            if not users:
                break

            def process(user):
                try:
                    analyze_user(user)
                    return True
                except Exception as e:
                    logger.error("用户 %s 分析失败: %s", user.account, e, exc_info=True)
                    return False

            with ThreadPoolExecutor(max_workers=workers) as executor:
                for ok in as_completed({executor.submit(process, u): u for u in users}):
                    if ok.result():
                        total_ok += 1
                    else:
                        total_fail += 1

            offset += len(users)
            if len(users) < batch_size:
                break

        status = "success"
    except Exception as e:
        status = "failed"
        error_summary = str(e)
        logger.error("任务执行异常: %s", e, exc_info=True)
    finally:
        _running = False

    end_time = datetime.now()
    total_users = total_ok + total_fail
    logger.info("任务完成：成功 %d，失败 %d，耗时 %s", total_ok, total_fail,
                str(end_time - start_time).split(".")[0])

    try:
        political_users = get_political_users()
        # 写入 key_focus_user 表
        upsert_key_focus_users(political_users)
    except Exception as e:
        logger.error("查询/写入涉政用户失败: %s", e)
        political_users = []

    send_task_report(
        status=status,
        start_time=start_time,
        end_time=end_time,
        total_users=total_users,
        success=total_ok,
        failed=total_fail,
        political_users=political_users,
        error_summary=error_summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="用户分析定时调度")
    parser.add_argument("--now", action="store_true", help="立即执行一次（不进入调度模式）")
    args = parser.parse_args()

    if args.now:
        run_analysis_job()
        return

    from apscheduler.schedulers.blocking import BlockingScheduler
    cfg = reload_config()
    schedule_cfg = cfg.get("scheduler", {})
    hour = schedule_cfg.get("hour", 18)
    minute = int(schedule_cfg.get("minute", 0))

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_analysis_job,
        trigger="cron",
        hour=hour,
        minute=minute,
        max_instances=1,
        id="daily_analysis",
    )
    logger.info("调度器启动，每天 %s:%02d 执行分析任务", hour, minute)
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("调度器已停止")


if __name__ == "__main__":
    main()
