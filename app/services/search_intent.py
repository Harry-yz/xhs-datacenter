from __future__ import annotations

import re
from collections.abc import Iterable

from app.services.industry_catalog import (
    STANDARD_INDUSTRIES,
    get_industry_keywords,
    resolve_industry_key,
)

_DEFAULT_INTENT_MAP: dict[str, tuple[str, ...]] = {
    "美妆个护": ("美妆", "个护", "护肤", "口红", "精华", "防晒", "粉底"),
    "beauty personal care": ("beauty", "personal care", "skincare", "makeup", "lipstick", "serum", "sunscreen"),
    "3c数码": ("3c", "数码", "手机", "电脑", "平板", "耳机", "相机"),
    "consumer electronics": ("electronics", "phone", "laptop", "tablet", "earbuds", "camera"),
    "服饰穿搭": ("服饰", "穿搭", "搭配", "鞋包", "外套", "连衣裙"),
    "fashion": ("fashion", "outfit", "ootd", "dress", "coat", "shoes"),
    "母婴亲子": ("母婴", "亲子", "育儿", "奶粉", "纸尿裤"),
    "食品饮料": ("食品", "饮料", "零食", "茶饮", "咖啡"),
    "家居家装": ("家居", "家装", "装修", "软装", "收纳"),
    "汽车出行": ("汽车", "新能源", "试驾", "出行", "SUV"),
    "运动户外": ("运动", "健身", "跑步", "露营", "徒步"),
    "医疗健康": ("医疗", "健康", "保健", "养生", "睡眠"),
    "教育培训": ("教育", "培训", "考研", "英语", "学习"),
    "文旅酒店": ("文旅", "酒店", "旅游", "民宿", "度假"),
}

_DEFAULT_STOP_WORDS = {
    "的",
    "了",
    "和",
    "与",
    "及",
    "在",
    "就",
    "很",
    "还",
    "也",
    "适合",
    "推荐",
    "怎么",
    "如何",
    "以及",
    "一个",
    "一下",
    "the",
    "a",
    "an",
    "for",
    "to",
    "of",
    "and",
    "with",
    "is",
    "are",
    "best",
}

_intent_map: dict[str, tuple[str, ...]] = dict(_DEFAULT_INTENT_MAP)
_stop_words: set[str] = set(_DEFAULT_STOP_WORDS)


def _normalize(value: str | None) -> str:
    return (value or "").strip()


def _dedupe_terms(terms: Iterable[str], *, max_terms: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        token = _normalize(str(raw))
        if not token:
            continue
        marker = token.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break
    return deduped


def _split_by_delimiter(text_value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\s,，;；、/|+]+", text_value) if item.strip()]


def _extract_sentence_terms(text_value: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text_value)
    expanded: list[str] = []
    for token in tokens:
        item = token.strip()
        if not item:
            continue
        expanded.append(item)
        # 中文长词再做 2~4 字窗口，提升大词召回。
        if re.fullmatch(r"[\u4e00-\u9fff]{5,}", item):
            for n in (2, 3, 4):
                if len(item) < n:
                    continue
                for i in range(0, len(item) - n + 1):
                    sub = item[i : i + n]
                    if sub:
                        expanded.append(sub)
    return expanded


def _apply_stop_words(tokens: Iterable[str]) -> list[str]:
    kept: list[str] = []
    for raw in tokens:
        token = _normalize(raw)
        if not token:
            continue
        marker = token.casefold()
        if marker in _stop_words:
            continue
        # 单字噪音过滤（但保留数字 token）
        if len(token) == 1 and not token.isdigit():
            continue
        kept.append(token)
    return kept


def _expand_by_dictionary(base: str) -> list[str]:
    lowered = base.casefold()
    terms: list[str] = []
    for key, values in _intent_map.items():
        key_lower = key.casefold()
        if key_lower in lowered or lowered in key_lower:
            terms.extend(values)
    return terms


def _expand_by_industry(industry: str | None) -> list[str]:
    industry_key = resolve_industry_key(industry)
    if not industry_key:
        return []
    return get_industry_keywords(industry_key)


def reload_intent_config(
    *,
    intent_map: dict[str, Iterable[str]] | None = None,
    stop_words: Iterable[str] | None = None,
) -> None:
    """Hot-reload search intent config in-process.

    This keeps rollout lightweight: update config source and call once.
    """

    global _intent_map, _stop_words

    if intent_map is None:
        merged = dict(_DEFAULT_INTENT_MAP)
    else:
        merged = {
            _normalize(key): tuple(_dedupe_terms(values, max_terms=64))
            for key, values in intent_map.items()
            if _normalize(key)
        }
    for industry in STANDARD_INDUSTRIES:
        if industry.name not in merged:
            merged[industry.name] = tuple(get_industry_keywords(industry.key))
    _intent_map = merged

    if stop_words is None:
        _stop_words = set(_DEFAULT_STOP_WORDS)
    else:
        _stop_words = {item.casefold() for item in stop_words if _normalize(str(item))}


def split_intent_terms(query: str, *, max_terms: int = 20, industry: str | None = None) -> list[str]:
    base = _normalize(query)
    if not base:
        return _expand_by_industry(industry)[:max_terms]

    candidates: list[str] = [base]
    candidates.extend(_expand_by_dictionary(base))
    candidates.extend(_split_by_delimiter(base))
    candidates.extend(_extract_sentence_terms(base))
    candidates.extend(_expand_by_industry(industry))
    cleaned = _apply_stop_words(candidates)
    return _dedupe_terms(cleaned, max_terms=max_terms)
