from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IndustryConfig:
    key: str
    name: str
    sort_no: int
    core_keywords: tuple[str, ...]
    brand_keywords: tuple[str, ...]
    scenario_keywords: tuple[str, ...]
    blacklist_keywords: tuple[str, ...] = ()


STANDARD_INDUSTRIES: tuple[IndustryConfig, ...] = (
    IndustryConfig(
        key="beauty",
        name="美妆个护",
        sort_no=10,
        core_keywords=("护肤", "彩妆", "防晒", "底妆", "精华", "面霜"),
        brand_keywords=("兰蔻", "雅诗兰黛", "欧莱雅", "安热沙", "YSL"),
        scenario_keywords=("通勤妆", "约会妆", "学生党美妆", "敏感肌修护"),
    ),
    IndustryConfig(
        key="fashion",
        name="服饰穿搭",
        sort_no=20,
        core_keywords=("穿搭", "ootd", "通勤穿搭", "显瘦", "外套", "鞋包"),
        brand_keywords=("优衣库", "ZARA", "太平鸟", "UR", "lululemon"),
        scenario_keywords=("春季穿搭", "秋冬穿搭", "职场穿搭", "约会穿搭"),
    ),
    IndustryConfig(
        key="mother_baby",
        name="母婴亲子",
        sort_no=30,
        core_keywords=("母婴", "育儿", "宝宝辅食", "亲子", "奶粉", "纸尿裤"),
        brand_keywords=("飞鹤", "伊利金领冠", "君乐宝", "帮宝适", "好奇"),
        scenario_keywords=("新生儿", "宝宝断奶", "早教", "亲子出行"),
    ),
    IndustryConfig(
        key="food_drink",
        name="食品饮料",
        sort_no=40,
        core_keywords=("零食", "饮料", "咖啡", "茶饮", "烘焙", "速食"),
        brand_keywords=("三只松鼠", "元气森林", "农夫山泉", "瑞幸", "喜茶"),
        scenario_keywords=("办公室零食", "减脂餐", "露营饮品", "下午茶"),
    ),
    IndustryConfig(
        key="home_living",
        name="家居家装",
        sort_no=50,
        core_keywords=("家居", "装修", "软装", "收纳", "家电", "家装"),
        brand_keywords=("宜家", "顾家家居", "索菲亚", "全友", "欧派"),
        scenario_keywords=("小户型", "客厅改造", "卧室收纳", "租房改造"),
    ),
    IndustryConfig(
        key="consumer_electronics",
        name="3C数码",
        sort_no=60,
        core_keywords=("手机", "电脑", "耳机", "平板", "相机", "数码"),
        brand_keywords=("苹果", "华为", "小米", "OPPO", "vivo"),
        scenario_keywords=("开箱", "评测", "续航", "拍照对比"),
    ),
    IndustryConfig(
        key="auto_travel",
        name="汽车出行",
        sort_no=70,
        core_keywords=("汽车", "新能源", "油耗", "试驾", "SUV", "出行"),
        brand_keywords=("比亚迪", "特斯拉", "理想", "小鹏", "问界"),
        scenario_keywords=("通勤代步", "长途自驾", "家庭用车", "车机体验"),
    ),
    IndustryConfig(
        key="sports_outdoor",
        name="运动户外",
        sort_no=80,
        core_keywords=("运动", "健身", "跑步", "露营", "徒步", "骑行"),
        brand_keywords=("耐克", "阿迪达斯", "迪卡侬", "始祖鸟", "安踏"),
        scenario_keywords=("减脂", "马拉松", "户外徒步", "城市骑行"),
    ),
    IndustryConfig(
        key="pet",
        name="宠物",
        sort_no=90,
        core_keywords=("宠物", "猫粮", "狗粮", "宠物用品", "养猫", "养狗"),
        brand_keywords=("皇家", "渴望", "巅峰", "伯纳天纯", "麦富迪"),
        scenario_keywords=("新手养猫", "宠物健康", "猫咪驱虫", "狗狗训练"),
    ),
    IndustryConfig(
        key="healthcare",
        name="医疗健康",
        sort_no=100,
        core_keywords=("健康管理", "营养", "体检", "保健", "养生", "睡眠"),
        brand_keywords=("汤臣倍健", "Swisse", "同仁堂", "维生素", "鱼油"),
        scenario_keywords=("熬夜恢复", "免疫提升", "体重管理", "久坐健康"),
    ),
    IndustryConfig(
        key="education",
        name="教育培训",
        sort_no=110,
        core_keywords=("教育", "培训", "考研", "英语学习", "职业教育", "学习方法"),
        brand_keywords=("新东方", "猿辅导", "作业帮", "学而思", "高途"),
        scenario_keywords=("备考", "留学", "求职提升", "职场英语"),
    ),
    IndustryConfig(
        key="travel_hotel",
        name="文旅酒店",
        sort_no=120,
        core_keywords=("旅游", "酒店", "民宿", "机票", "攻略", "度假"),
        brand_keywords=("携程", "飞猪", "同程", "万豪", "希尔顿"),
        scenario_keywords=("周末短途", "亲子旅行", "海岛度假", "citywalk"),
    ),
)


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for raw in items:
        value = str(raw).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


_TOKEN_SPLIT_PATTERN = re.compile(r"[\s,，;；、/|+]+")
_TEXT_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}")
_STOP_WORDS = {
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
}

_tables_ready = False


def _normalize_token(value: str | None) -> str:
    return str(value or "").strip()


def _expand_text_tokens(text_value: str) -> list[str]:
    tokens = _TEXT_TOKEN_PATTERN.findall(text_value)
    expanded: list[str] = []
    for token in tokens:
        item = token.strip()
        if not item:
            continue
        expanded.append(item)
        if re.fullmatch(r"[\u4e00-\u9fff]{5,}", item):
            for n in (2, 3, 4):
                if len(item) < n:
                    continue
                for idx in range(0, len(item) - n + 1):
                    expanded.append(item[idx : idx + n])
    return expanded


def _tokenize_fragments(fragments: Iterable[str], *, max_terms: int = 160) -> list[str]:
    candidates: list[str] = []
    for fragment in fragments:
        text_value = _normalize_token(fragment)
        if not text_value:
            continue
        candidates.append(text_value)
        candidates.extend([part for part in _TOKEN_SPLIT_PATTERN.split(text_value) if part])
        candidates.extend(_expand_text_tokens(text_value))

    output: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        token = _normalize_token(raw)
        if not token:
            continue
        marker = token.casefold()
        if marker in _STOP_WORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        if marker in seen:
            continue
        seen.add(marker)
        output.append(token)
        if len(output) >= max_terms:
            break
    return output


def get_industry_by_key(industry_key: str) -> IndustryConfig | None:
    key = industry_key.strip().lower()
    for item in STANDARD_INDUSTRIES:
        if item.key == key:
            return item
    return None


def resolve_industry_key(industry_value: str | None) -> str | None:
    if industry_value in (None, ""):
        return None

    target = str(industry_value).strip()
    if not target:
        return None

    for item in STANDARD_INDUSTRIES:
        if target.casefold() in {item.key.casefold(), item.name.casefold()}:
            return item.key
    return None


def get_all_industry_keywords() -> list[str]:
    values: list[str] = []
    for item in STANDARD_INDUSTRIES:
        values.extend(item.core_keywords)
        values.extend(item.brand_keywords)
        values.extend(item.scenario_keywords)
    return _dedupe(values)


def get_industry_keywords(industry_key: str) -> list[str]:
    industry = get_industry_by_key(industry_key)
    if not industry:
        return []
    return _dedupe((*industry.core_keywords, *industry.brand_keywords, *industry.scenario_keywords))


def ensure_industry_tables(db: Session) -> None:
    global _tables_ready
    if _tables_ready:
        return

    def _safe_ddl(ddl: str) -> None:
        try:
            db.execute(text(ddl))
        except Exception as exc:
            message = str(exc).lower()
            if "pg_type_typname_nsp_index" in message or "already exists" in message:
                db.rollback()
                return
            raise

    _safe_ddl(
        """
            CREATE TABLE IF NOT EXISTS xhs_industry_dim (
                industry_key varchar(64) PRIMARY KEY,
                industry_name varchar(100) NOT NULL UNIQUE,
                sort_no integer NOT NULL DEFAULT 100,
                status varchar(20) NOT NULL DEFAULT 'enabled',
                keyword_count integer NOT NULL DEFAULT 0,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
        """,
    )
    _safe_ddl(
        """
            CREATE TABLE IF NOT EXISTS xhs_industry_keyword_dim (
                id bigserial PRIMARY KEY,
                industry_key varchar(64) NOT NULL REFERENCES xhs_industry_dim(industry_key),
                keyword varchar(255) NOT NULL,
                keyword_type varchar(32) NOT NULL,
                is_blacklist boolean NOT NULL DEFAULT false,
                priority integer NOT NULL DEFAULT 100,
                status varchar(20) NOT NULL DEFAULT 'enabled',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE(industry_key, keyword, is_blacklist)
            )
        """,
    )
    _safe_ddl(
        """
            CREATE TABLE IF NOT EXISTS xhs_brand_alias_dim (
                id bigserial PRIMARY KEY,
                brand_name varchar(255) NOT NULL,
                alias varchar(255) NOT NULL,
                industry_key varchar(64),
                status varchar(20) NOT NULL DEFAULT 'enabled',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE(brand_name, alias)
            )
        """,
    )
    _safe_ddl(
        """
            CREATE TABLE IF NOT EXISTS xhs_note_industry_rel (
                id bigserial PRIMARY KEY,
                note_id varchar(64) NOT NULL,
                industry_key varchar(64) NOT NULL REFERENCES xhs_industry_dim(industry_key),
                matched_keyword varchar(255) NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE(note_id, industry_key)
            )
        """,
    )
    _safe_ddl("CREATE INDEX IF NOT EXISTS idx_xhs_note_industry_rel_note ON xhs_note_industry_rel(note_id)")
    _safe_ddl("CREATE INDEX IF NOT EXISTS idx_xhs_note_industry_rel_industry ON xhs_note_industry_rel(industry_key)")
    _tables_ready = True


def sync_industry_catalog(db: Session) -> dict[str, int]:
    ensure_industry_tables(db)

    industry_rows = 0
    keyword_rows = 0
    brand_alias_rows = 0

    for industry in STANDARD_INDUSTRIES:
        keywords = _dedupe((*industry.core_keywords, *industry.brand_keywords, *industry.scenario_keywords))
        db.execute(
            text(
                """
                INSERT INTO xhs_industry_dim(industry_key, industry_name, sort_no, status, keyword_count)
                VALUES(:industry_key, :industry_name, :sort_no, 'enabled', :keyword_count)
                ON CONFLICT (industry_key) DO UPDATE SET
                    industry_name = EXCLUDED.industry_name,
                    sort_no = EXCLUDED.sort_no,
                    status = EXCLUDED.status,
                    keyword_count = EXCLUDED.keyword_count,
                    updated_at = now()
                """
            ),
            {
                "industry_key": industry.key,
                "industry_name": industry.name,
                "sort_no": industry.sort_no,
                "keyword_count": len(keywords),
            },
        )
        industry_rows += 1

        for keyword in _dedupe(industry.core_keywords):
            db.execute(
                text(
                    """
                    INSERT INTO xhs_industry_keyword_dim(industry_key, keyword, keyword_type, is_blacklist, priority)
                    VALUES(:industry_key, :keyword, 'core', false, 10)
                    ON CONFLICT (industry_key, keyword, is_blacklist) DO UPDATE SET
                        keyword_type = EXCLUDED.keyword_type,
                        priority = EXCLUDED.priority,
                        status = 'enabled',
                        updated_at = now()
                    """
                ),
                {"industry_key": industry.key, "keyword": keyword},
            )
            keyword_rows += 1

        for keyword in _dedupe(industry.brand_keywords):
            db.execute(
                text(
                    """
                    INSERT INTO xhs_industry_keyword_dim(industry_key, keyword, keyword_type, is_blacklist, priority)
                    VALUES(:industry_key, :keyword, 'brand', false, 20)
                    ON CONFLICT (industry_key, keyword, is_blacklist) DO UPDATE SET
                        keyword_type = EXCLUDED.keyword_type,
                        priority = EXCLUDED.priority,
                        status = 'enabled',
                        updated_at = now()
                    """
                ),
                {"industry_key": industry.key, "keyword": keyword},
            )
            keyword_rows += 1

            db.execute(
                text(
                    """
                    INSERT INTO xhs_brand_alias_dim(brand_name, alias, industry_key, status)
                    VALUES(:brand_name, :alias, :industry_key, 'enabled')
                    ON CONFLICT (brand_name, alias) DO UPDATE SET
                        industry_key = EXCLUDED.industry_key,
                        status = 'enabled',
                        updated_at = now()
                    """
                ),
                {"brand_name": keyword, "alias": keyword, "industry_key": industry.key},
            )
            brand_alias_rows += 1

        for keyword in _dedupe(industry.scenario_keywords):
            db.execute(
                text(
                    """
                    INSERT INTO xhs_industry_keyword_dim(industry_key, keyword, keyword_type, is_blacklist, priority)
                    VALUES(:industry_key, :keyword, 'scenario', false, 30)
                    ON CONFLICT (industry_key, keyword, is_blacklist) DO UPDATE SET
                        keyword_type = EXCLUDED.keyword_type,
                        priority = EXCLUDED.priority,
                        status = 'enabled',
                        updated_at = now()
                    """
                ),
                {"industry_key": industry.key, "keyword": keyword},
            )
            keyword_rows += 1

        for keyword in _dedupe(industry.blacklist_keywords):
            db.execute(
                text(
                    """
                    INSERT INTO xhs_industry_keyword_dim(industry_key, keyword, keyword_type, is_blacklist, priority)
                    VALUES(:industry_key, :keyword, 'blacklist', true, 1000)
                    ON CONFLICT (industry_key, keyword, is_blacklist) DO UPDATE SET
                        keyword_type = EXCLUDED.keyword_type,
                        priority = EXCLUDED.priority,
                        status = 'enabled',
                        updated_at = now()
                    """
                ),
                {"industry_key": industry.key, "keyword": keyword},
            )
            keyword_rows += 1

    db.commit()
    return {
        "industry_count": industry_rows,
        "keyword_count": keyword_rows,
        "brand_alias_count": brand_alias_rows,
    }


def match_note_industries_by_keyword(db: Session, *, note_id: str, search_keyword: str) -> int:
    return match_note_industries(
        db,
        note_id=note_id,
        search_keyword=search_keyword,
    )


def match_note_industries(
    db: Session,
    *,
    note_id: str,
    search_keyword: str | None = None,
    title: str | None = None,
    content: str | None = None,
    tags: Iterable[str] | None = None,
    brand_aliases: Iterable[str] | None = None,
) -> int:
    token_fragments: list[str] = []
    if search_keyword:
        token_fragments.append(str(search_keyword))
    if title:
        token_fragments.append(str(title))
    if content:
        token_fragments.append(str(content))
    if tags:
        token_fragments.extend([str(tag) for tag in tags if str(tag).strip()])
    if brand_aliases:
        token_fragments.extend([str(alias) for alias in brand_aliases if str(alias).strip()])

    terms = _tokenize_fragments(token_fragments)
    if not terms:
        return 0

    keyword_rows = db.execute(
        text(
            """
            SELECT industry_key, keyword, is_blacklist, priority
            FROM xhs_industry_keyword_dim
            WHERE status = 'enabled'
              AND keyword = ANY(CAST(:terms AS text[]))
            """
        ),
        {"terms": terms},
    ).mappings().all()

    alias_rows = db.execute(
        text(
            """
            SELECT industry_key, alias
            FROM xhs_brand_alias_dim
            WHERE status = 'enabled'
              AND alias = ANY(CAST(:terms AS text[]))
            """
        ),
        {"terms": terms},
    ).mappings().all()

    if not keyword_rows and not alias_rows:
        return 0

    rank_by_token = {value.casefold(): index for index, value in enumerate(terms)}
    blocked_industries: set[str] = set()
    winners: dict[str, tuple[int, str]] = {}

    def _update_winner(industry_key: str, matched_keyword: str, score: int) -> None:
        current = winners.get(industry_key)
        if current is None or score < current[0]:
            winners[industry_key] = (score, matched_keyword)

    for row in keyword_rows:
        industry_key = str(row.get("industry_key") or "").strip()
        matched_keyword = str(row.get("keyword") or "").strip()
        if not industry_key or not matched_keyword:
            continue
        if row.get("is_blacklist"):
            blocked_industries.add(industry_key)
            continue

        token_rank = rank_by_token.get(matched_keyword.casefold(), len(terms) + 50)
        priority = int(row.get("priority") or 100)
        score = token_rank + (priority * 100)
        _update_winner(industry_key, matched_keyword, score)

    for row in alias_rows:
        industry_key = str(row.get("industry_key") or "").strip()
        alias = str(row.get("alias") or "").strip()
        if not industry_key or not alias:
            continue
        token_rank = rank_by_token.get(alias.casefold(), len(terms) + 50)
        score = -1000 + token_rank
        _update_winner(industry_key, alias, score)

    for industry_key in blocked_industries:
        winners.pop(industry_key, None)

    if not winners:
        return 0

    rows = sorted(winners.items(), key=lambda item: item[1][0])
    inserted = 0
    for industry_key, (_, matched_keyword) in rows:
        db.execute(
            text(
                """
                INSERT INTO xhs_note_industry_rel(note_id, industry_key, matched_keyword)
                VALUES(:note_id, :industry_key, :matched_keyword)
                ON CONFLICT (note_id, industry_key) DO UPDATE SET
                    matched_keyword = EXCLUDED.matched_keyword,
                    updated_at = now()
                """
            ),
            {"note_id": note_id, "industry_key": industry_key, "matched_keyword": matched_keyword},
        )
        inserted += 1
    return inserted
