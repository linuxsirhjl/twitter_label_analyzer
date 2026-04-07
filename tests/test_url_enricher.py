"""
tests/test_url_enricher.py

测试 URL 内容展开模块（url_enricher.py）。
使用真实网络请求，不使用 mock。
从数据库读取真实推文数据进行验证。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.db import fetch_all
from app.services.url_enricher import enrich_text, _expand_url, _fetch_page_summary

_URL_RE = re.compile(r"https?://\S+")

# ── 辅助函数 ──────────────────────────────────────────────────


def fetch_test_texts() -> list[dict]:
    """从数据库读取 id in (38..44) 的推文记录。"""
    sql = (
        "SELECT id, `被回复或转发帖子内容` AS text "
        "FROM `users_tweets` "
        "WHERE id IN (8288, 8289, 8290, 8291, 8292, 8293, 8294)"
    )
    return fetch_all(sql)


def classify_url_type(url: str) -> str:
    """根据 URL 路径后缀判断内容类型。"""
    path = urlparse(url).path.lower()
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "图片"
    if any(path.endswith(ext) for ext in (".mp4", ".mov", ".avi", ".m3u8")):
        return "视频"
    return "HTML"


def run_single_test(row: dict) -> dict:
    """
    对单条推文执行 URL 展开与内容抓取，返回测试结果字典。

    Returns:
        dict with keys: id, original, enriched, urls, expanded_urls,
                        url_type, content_preview, expanded_ok, content_ok
    """
    record_id = row["id"]
    original: str = row["text"] or ""
    urls = _URL_RE.findall(original)

    # 展开 URL（用于日志输出）
    expanded_urls = []
    url_types = []
    for url in urls:
        try:
            real = _expand_url(url)
            expanded_urls.append(real)
            url_types.append(classify_url_type(real))
        except Exception:
            expanded_urls.append(url)
            url_types.append("未知")

    # 抓取增强文本
    enriched = enrich_text(original)

    # 抓取内容预览（取第一个 URL 的摘要）
    content_preview = ""
    if expanded_urls:
        try:
            content_preview = _fetch_page_summary(expanded_urls[0])[:200]
        except Exception:
            pass

    expanded_ok = len(expanded_urls) > 0 and any(u != o for u, o in zip(expanded_urls, urls))
    content_ok = "[链接内容摘要]" in enriched and len(enriched) > len(original)

    return {
        "id": record_id,
        "original": original,
        "enriched": enriched,
        "urls": urls,
        "expanded_urls": expanded_urls,
        "url_types": url_types,
        "content_preview": content_preview,
        "expanded_ok": expanded_ok,
        "content_ok": content_ok,
    }


def print_result(result: dict) -> None:
    """格式化打印单条测试结果。"""
    print("=" * 60)
    print(f"记录 ID：{result['id']}")
    print(f"\n原始文本：\n{result['original']}")
    print(f"\n增强后文本：\n{result['enriched'][:500]}{'...' if len(result['enriched']) > 500 else ''}")
    for orig, real, t in zip(result["urls"], result["expanded_urls"], result["url_types"]):
        print(f"\n  原始 URL：{orig}")
        print(f"  展开 URL：{real}")
        print(f"  内容类型：{t}")
    if result["content_preview"]:
        print(f"\n抓取内容前200字：\n{result['content_preview']}")
    print(f"\n是否成功展开：{result['expanded_ok']}")
    print(f"是否抓取到内容：{result['content_ok']}")


# ── 测试函数 ──────────────────────────────────────────────────


def test_url_enrichment() -> None:
    """主测试：对数据库中7条真实推文验证 URL 展开与内容抓取。"""
    rows = fetch_test_texts()
    assert len(rows) > 0, "数据库中未找到测试数据（id 38-44）"

    results = [run_single_test(r) for r in rows]

    for r in results:
        print_result(r)

    # 统计
    total = len(results)
    content_ok_count = sum(1 for r in results if r["content_ok"])
    expanded_ok_count = sum(1 for r in results if r["expanded_ok"])

    # 按类型分类统计
    type_counts: dict[str, int] = {}
    for r in results:
        for t in r["url_types"]:
            type_counts[t] = type_counts.get(t, 0) + 1

    print("\n" + "=" * 60)
    print("📊 统计结果")
    print(f"  总条数：{total}")
    print(f"  成功展开 URL：{expanded_ok_count}/{total}")
    print(f"  成功抓取内容：{content_ok_count}/{total}  ({content_ok_count/total*100:.0f}%)")
    print(f"  内容类型分布：{type_counts}")

    # 断言：至少一半成功（网络环境可能部分失败）
    assert content_ok_count >= total // 2, (
        f"内容抓取成功率过低：{content_ok_count}/{total}"
    )


def test_no_url_text() -> None:
    """无 URL 文本：enrich_text 应返回原始文本，不添加摘要。"""
    text = "这是一个普通文本，没有任何链接"
    result = enrich_text(text)
    print(f"\n[无URL测试] 输入：{text}")
    print(f"[无URL测试] 输出：{result}")
    assert result == text, "无 URL 文本不应被修改"
    assert "[链接内容摘要]" not in result


def test_invalid_url() -> None:
    """无效 URL：不应抛出异常，返回原始文本或轻微变化。"""
    text = "test https://t.co/invalid_url_xyz_404"
    try:
        result = enrich_text(text)
        print(f"\n[无效URL测试] 输入：{text}")
        print(f"[无效URL测试] 输出：{result}")
        # 不报错即通过，内容可能未变化
        assert isinstance(result, str)
    except Exception as e:
        raise AssertionError(f"无效 URL 不应抛出异常: {e}") from e
