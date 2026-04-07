"""URL 内容展开与提取模块。

当前支持：
- t.co 短链展开
- 网页 title / meta description 提取
- 正文 fallback 提取

预留接口（后续扩展）：
- enrich_image(url) -> str   图片 OCR
- enrich_video(url) -> str   视频摘要
- enrich_multimodal(url) -> str  多模态分析
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.settings import get_config

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+")
_TIMEOUT = 5.0
_MAX_CONTENT_CHARS = 2000
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _get_proxies() -> dict | None:
    """从配置读取代理，未启用则返回 None。"""
    try:
        cfg = get_config()
        proxy_cfg = cfg.get("proxy", {})
        if not proxy_cfg.get("enabled", False):
            return None
        return {
            "http": proxy_cfg.get("http", ""),
            "https": proxy_cfg.get("https", ""),
        }
    except Exception:
        return None


def _expand_url(url: str) -> str:
    """跟随跳转，返回最终真实 URL。"""
    proxies = _get_proxies()
    try:
        resp = requests.get(url, allow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS, proxies=proxies)
        real = resp.url
        logger.debug("URL 展开: %s -> %s (status=%d, redirected=%s)",
                     url, real, resp.status_code, real != url)
        return real
    except Exception as e:
        logger.debug("URL 展开失败 %s: %s", url, e)
        try:
            resp = requests.head(url, allow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS, proxies=proxies)
            return resp.url
        except Exception:
            return url


def _fetch_page_summary(url: str) -> str:
    """抓取页面，优先返回 title + meta description，fallback 正文文本。"""
    proxies = _get_proxies()
    try:
        resp = requests.get(url, allow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS, proxies=proxies)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "text/html" not in ct and "text/" not in ct:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        parts: list[str] = []
        if soup.title and soup.title.string:
            parts.append(soup.title.string.strip())
        meta = soup.find("meta", attrs={"name": "description"}) or \
               soup.find("meta", attrs={"property": "og:description"})
        if meta and meta.get("content"):  # type: ignore[union-attr]
            parts.append(meta["content"].strip())  # type: ignore[index]
        if not parts:
            text = soup.get_text(separator=" ", strip=True)
            parts.append(text[:_MAX_CONTENT_CHARS])
        return " | ".join(parts)[:_MAX_CONTENT_CHARS]
    except Exception as e:
        logger.debug("抓取页面失败 %s: %s", url, e)
        return ""


def _is_media_url(url: str) -> bool:
    """判断是否为图片/视频等媒体链接（暂不处理）。"""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi"))


def enrich_text(text: str) -> str:
    """
    检测文本中的 URL，展开并提取内容，拼接到原始文本后返回。
    若无 URL 或全部抓取失败，返回原始文本。
    """
    urls = _URL_RE.findall(text)
    if not urls:
        return text

    additions: list[str] = []
    for url in urls:
        try:
            real_url = _expand_url(url)
            logger.debug("URL 展开: %s -> %s", url, real_url)
            if _is_media_url(real_url):
                # 预留：后续接 enrich_image / enrich_video
                continue
            summary = _fetch_page_summary(real_url)
            if summary:
                additions.append(f"[链接内容摘要]\n{summary}")
        except Exception as e:
            logger.debug("URL 处理异常 %s: %s", url, e)

    if not additions:
        return text
    return text + "\n\n" + "\n\n".join(additions)


# ── 预留扩展接口 ──────────────────────────────────────────────

def enrich_image(url: str) -> str:  # noqa: ARG001
    """图片 OCR（待实现）。"""
    raise NotImplementedError


def enrich_video(url: str) -> str:  # noqa: ARG001
    """视频摘要（待实现）。"""
    raise NotImplementedError


def enrich_multimodal(url: str) -> str:  # noqa: ARG001
    """多模态分析（待实现）。"""
    raise NotImplementedError
