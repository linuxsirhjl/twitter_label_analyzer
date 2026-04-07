"""数据模型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BasicUserInfo:
    id: int
    account: str
    account_id: str
    nickname: str
    bio: str
    total_likes: int | None
    following_count: int | None
    followers_count: int | None
    posts_count: int | None
    media_count: int | None
    is_private: bool | None
    location: str
    link: str
    birth_year: str
    profession: str
    is_subscribed: bool | None
    user_category: str
    user_profile_summary: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BasicUserInfo":
        return cls(
            id=row["id"],
            account=row.get("账号") or "",
            account_id=row.get("账号ID") or "",
            nickname=row.get("昵称") or "",
            bio=row.get("用户简介") or "",
            total_likes=row.get("总点赞数"),
            following_count=row.get("正在关注数"),
            followers_count=row.get("总关注者"),
            posts_count=row.get("帖子数"),
            media_count=row.get("媒体发布数"),
            is_private=row.get("是否设为私密"),
            location=row.get("用户提供的定位") or "",
            link=row.get("用户提供的链接") or "",
            birth_year=row.get("用户提供的出生年份") or "",
            profession=row.get("用户提供的专业领域") or "",
            is_subscribed=row.get("是否付费订阅用户"),
            user_category=row.get("user_category") or "",
            user_profile_summary=row.get("user_profile_summary") or "",
        )


@dataclass
class TweetRecord:
    text: str


@dataclass
class ReplyRecord:
    text: str


@dataclass
class FollowingRecord:
    account: str
    nickname: str
    bio: str


@dataclass
class FollowerRecord:
    account: str


@dataclass
class UserAnalysisInput:
    user: BasicUserInfo
    tweets: list[TweetRecord] = field(default_factory=list)
    replies: list[ReplyRecord] = field(default_factory=list)
    following: list[FollowingRecord] = field(default_factory=list)
    followers: list[FollowerRecord] = field(default_factory=list)


@dataclass
class UserAnalysisResult:
    user_id: int
    account: str
    labels: list[str]
    profile_summary: str
    reasoning_brief: str = ""
