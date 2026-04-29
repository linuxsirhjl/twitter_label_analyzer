"""用户分析编排服务：汇总数据、规则预判、LLM 判定、回写。"""
from __future__ import annotations

import logging
import time

from app.models import BasicUserInfo, UserAnalysisInput, UserAnalysisResult
from app.repositories.followers_repository import get_followers_by_user
from app.repositories.following_repository import get_following_by_user
from app.repositories.replies_repository import get_replies_by_user
from app.repositories.screenshot_repository import get_screenshot_paths_by_user
from app.repositories.tweets_repository import get_tweets_by_user
from app.repositories.user_repository import update_user_analysis
from app.services.label_normalizer import normalize_labels
from app.services.llm_classifier import classify_user
from app.services.rule_engine import run_rule_check
from app.services.text_cleaner import clean_text, deduplicate_texts
from app.services.translator_service import translate_if_needed
from app.services.url_enricher import enrich_text
from app.settings import get_config
from app.utils.retry import retry

logger = logging.getLogger(__name__)


def _prepare_texts(analysis_input: UserAnalysisInput) -> UserAnalysisInput:
    """清洗、翻译、去重文本，保留链接信息。"""
    cfg = get_config()
    analysis_cfg = cfg.get("analysis", {})
    max_len = int(analysis_cfg.get("max_text_length", 1000))
    max_tweets = int(analysis_cfg.get("max_tweets_per_user", 20))
    max_replies = int(analysis_cfg.get("max_replies_per_user", 20))

    def process_with_links(records: list) -> list:
        """处理文本但保留链接信息"""
        from app.models import TweetRecord, ReplyRecord
        result = []
        for record in records:
            cleaned = clean_text(record.text, max_len)
            if cleaned:
                enriched = enrich_text(cleaned)
                translated = translate_if_needed(enriched)
                # 保留原始链接
                if isinstance(record, TweetRecord):
                    result.append(TweetRecord(text=translated, link=record.link))
                else:
                    result.append(ReplyRecord(text=translated, link=record.link))
        return result

    analysis_input.tweets = process_with_links(analysis_input.tweets[:max_tweets])
    analysis_input.replies = process_with_links(analysis_input.replies[:max_replies])
    return analysis_input


def analyze_user(user: BasicUserInfo) -> UserAnalysisResult:
    """
    对单个用户执行完整分析流程：
    1. 拉取关联数据
    2. 清洗文本
    3. 规则预判
    4. LLM 判定
    5. 标签归一化
    6. 回写数据库
    """
    user_start_time = time.time()
    cfg = get_config()
    analysis_cfg = cfg.get("analysis", {})
    max_tweets = int(analysis_cfg.get("max_tweets_per_user", 20))
    max_replies = int(analysis_cfg.get("max_replies_per_user", 20))

    logger.info("开始分析用户 id=%d 账号=%s", user.id, user.account)

    # 拉取关联数据
    tweets = get_tweets_by_user(user.account_id, user.account, limit=max_tweets)
    replies = get_replies_by_user(user.account_id, user.account, limit=max_replies)
    following = get_following_by_user(user.account_id, user.account)
    followers = get_followers_by_user(user.account_id, user.account)

    logger.info(
        "用户 %s 数据: tweets=%d replies=%d following=%d followers=%d",
        user.account, len(tweets), len(replies), len(following), len(followers),
    )

    analysis_input = UserAnalysisInput(
        user=user,
        tweets=tweets,
        replies=replies,
        following=following,
        followers=followers,
    )

    # 清洗文本
    analysis_input = _prepare_texts(analysis_input)

    # 查询截图路径
    screenshot_infos = get_screenshot_paths_by_user(user.account_id, user.account)
    logger.info("用户 %s 找到 %d 张截图", user.account, len(screenshot_infos))

    # 规则预判
    rule_labels = run_rule_check(analysis_input)
    logger.info("用户 %s 规则候选标签: %s", user.account, rule_labels)

    # LLM 判定
    max_retries = int(cfg.get("max_retries", 3))
    llm_start = time.time()
    llm_result = retry(
        lambda: classify_user(analysis_input, rule_labels, screenshot_infos),
        max_attempts=max_retries,
        delay=2.0,
        exceptions=(Exception,),
        label=f"LLM classify user={user.account}",
    )
    llm_elapsed = time.time() - llm_start

    # 合并规则标签和 LLM 标签
    merged_labels = list(set(rule_labels) | set(llm_result.get("labels", [])))
    final_labels = normalize_labels(merged_labels)
    profile_summary = llm_result.get("profile_summary", "")
    reasoning = llm_result.get("reasoning_brief", "")

    logger.info("用户 %s 最终标签: %s  LLM耗时: %.1fs  推理: %s", user.account, final_labels, llm_elapsed, reasoning)

    # 回写数据库
    category_str = ",".join(final_labels)
    retry(
        lambda: update_user_analysis(user.id, category_str, profile_summary),
        max_attempts=max_retries,
        delay=2.0,
        exceptions=(Exception,),
        label=f"DB write user={user.account}",
    )

    user_total_time = time.time() - user_start_time
    logger.info("用户 %s 分析完成，总耗时: %.1fs", user.account, user_total_time)

    return UserAnalysisResult(
        user_id=user.id,
        account=user.account,
        labels=final_labels,
        profile_summary=profile_summary,
        reasoning_brief=reasoning,
    )
