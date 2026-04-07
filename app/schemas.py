from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    code: int = 200
    message: str = "ok"
    data: Any | None = None


class SearchTriggerRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=255)
    sort: Literal[0, 1] = 1
    auto_enrich: bool = True
    trigger_comments: bool = False
    max_items: int = Field(default=20, ge=1, le=100)


class SearchCategoryRequest(BaseModel):
    category: str = Field(min_length=1, max_length=255)
    sort: Literal[0, 1] = 1
    force_refresh: bool = False
    freshness_hours: int = Field(default=24, ge=1, le=168)
    auto_enrich: bool = True
    trigger_comments: bool = False
    max_items: int = Field(default=20, ge=1, le=100)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class InfluencerSearchRequest(BaseModel):
    query: str = Field(default="", max_length=255)
    industry: str | None = Field(default=None, max_length=100)
    follower_range: str | None = Field(default=None, max_length=64, description="min,max")
    interaction_range: str | None = Field(default=None, max_length=64, description="min,max")
    sort: Literal["relevance", "followers", "notes", "sumStat"] = "relevance"
    order: Literal["asc", "desc"] = "desc"
    date_range: Literal[7, 30, 90] = 30
    freshness_hours: int = Field(default=24, ge=1, le=168)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    include_notes: bool = False
    force_refresh: bool = False


class BrandCategorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    mode: Literal["brand", "category"]
    industry: str | None = Field(default=None, max_length=100)
    min_like: int = Field(default=0, ge=0)
    sort: Literal["stat", "like", "read", "comments"] = "stat"
    order: Literal["asc", "desc"] = "desc"
    date_range: Literal[7, 30, 90] = 30
    freshness_hours: int = Field(default=24, ge=1, le=168)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    force_refresh: bool = False


class NoteTriggerRequest(BaseModel):
    note_id: str = Field(min_length=1, max_length=128)


class AnchorTriggerRequest(BaseModel):
    anchor_id: str = Field(min_length=1, max_length=128)


class KeywordAnalysisTriggerRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=255)
    last_days: Literal[7, 30, 90]
    priority: int = Field(default=3, ge=1, le=10)
    note_type: int | None = Field(default=None, ge=0, le=1)
    business: int | None = Field(default=None, ge=0, le=1)
    goods: int | None = Field(default=None, ge=0, le=1)
    max_note_num: int | None = Field(default=None, ge=1)


class BrandAnalysisTriggerRequest(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)
    priority: int = Field(default=3, ge=1, le=10)
    last_days: Literal[7, 30, 90] = 30


class BrandAccountsRequest(BaseModel):
    brand_name: str = Field(min_length=1, max_length=255)


class Pagination(BaseModel):
    total: int
    page: int
    size: int
    has_more: bool
    total_is_estimate: bool = False


class NoteListItem(BaseModel):
    note_id: str
    title: str | None = None
    author_id: str | None = None
    author_nickname: str | None = None
    read_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    collection_count: int = 0
    share_count: int = 0
    post_url: str | None = None
    publish_time: str | None = None
    tags: list[str] = []
