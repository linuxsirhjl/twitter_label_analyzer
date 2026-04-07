"""重试工具。"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry(
    func: Callable[[], T],
    *,
    max_attempts: int = 3,
    delay: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    label: str = "",
) -> T:
    """重试执行 func，失败时等待 delay 秒后重试，超过 max_attempts 则抛出最后一次异常。"""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except exceptions as e:
            last_exc = e
            if attempt < max_attempts:
                logger.warning(
                    "第 %d/%d 次尝试失败%s: %s，%.1f 秒后重试",
                    attempt, max_attempts, f" [{label}]" if label else "", e, delay,
                )
                time.sleep(delay)
            else:
                logger.error("已达最大重试次数%s: %s", f" [{label}]" if label else "", e)
    raise last_exc  # type: ignore[misc]
