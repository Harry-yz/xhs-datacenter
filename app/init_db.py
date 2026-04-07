from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    func,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from app.config import get_settings

settings = get_settings()
metadata = MetaData()

# ODS 原始层
ods_note_raw = Table(
    "ods_note_raw",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("task_type", String(64), nullable=False, default="note_info"),
    Column("batch_id", String(64)),
    Column("task_id", String(128)),
    Column("source_key", String(128)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

ods_anchor_raw = Table(
    "ods_anchor_raw",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("task_type", String(64), nullable=False, default="anchor_info"),
    Column("batch_id", String(64)),
    Column("task_id", String(128)),
    Column("source_key", String(128)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

ods_comment_raw = Table(
    "ods_comment_raw",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("task_type", String(64), nullable=False, default="note_comment"),
    Column("batch_id", String(64)),
    Column("task_id", String(128)),
    Column("source_key", String(128)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

ods_fans_raw = Table(
    "ods_fans_raw",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("task_type", String(64), nullable=False, default="fans_portrait"),
    Column("batch_id", String(64)),
    Column("task_id", String(128)),
    Column("source_key", String(128)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

ods_keyword_raw = Table(
    "ods_keyword_raw",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("task_type", String(64), nullable=False, default="keyword_analysis"),
    Column("batch_id", String(64)),
    Column("task_id", String(128)),
    Column("source_key", String(128)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

ods_brand_raw = Table(
    "ods_brand_raw",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("task_type", String(64), nullable=False, default="brand_analysis"),
    Column("batch_id", String(64)),
    Column("task_id", String(128)),
    Column("source_key", String(128)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

# DWD 明细层
xhs_note_fact = Table(
    "xhs_note_fact",
    metadata,
    Column("note_id", String(64), primary_key=True),
    Column("title", Text),
    Column("content", Text),
    Column("post_url", Text),
    Column("publish_time", DateTime(timezone=True)),
    Column("media_type", String(32)),
    Column("duration_seconds", Integer),
    Column("tags", ARRAY(Text), nullable=False, server_default="{}"),
    Column("media_urls", JSONB),
    Column("cover_image_url", Text),
    Column("read_count", BigInteger, nullable=False, server_default="0"),
    Column("like_count", BigInteger, nullable=False, server_default="0"),
    Column("comment_count", BigInteger, nullable=False, server_default="0"),
    Column("collection_count", BigInteger, nullable=False, server_default="0"),
    Column("share_count", BigInteger, nullable=False, server_default="0"),
    Column("interaction_total", BigInteger, nullable=False, server_default="0"),
    Column("stat_count", BigInteger, nullable=False, server_default="0"),
    Column("exp_count", BigInteger, nullable=False, server_default="0"),
    Column("ext_payload", JSONB),
    Column("author_id", String(128)),
    Column("author_nickname", String(255)),
    Column("author_fans_count", BigInteger),
    Column("search_keyword", String(255)),
    Column("search_rank", Integer),
    Column("search_type", String(64)),
    Column("batch_id", String(64)),
    Column("source_task_id", String(128)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("idx_xhs_note_fact_publish_time", xhs_note_fact.c.publish_time)
Index("idx_xhs_note_fact_author_id", xhs_note_fact.c.author_id)
Index("idx_xhs_note_fact_search_keyword", xhs_note_fact.c.search_keyword)
Index("idx_xhs_note_fact_interaction_total", xhs_note_fact.c.interaction_total)
Index("idx_xhs_note_fact_like_count", xhs_note_fact.c.like_count)
Index("idx_xhs_note_fact_comment_count", xhs_note_fact.c.comment_count)
Index("idx_xhs_note_fact_collection_count", xhs_note_fact.c.collection_count)
Index("idx_xhs_note_fact_read_count", xhs_note_fact.c.read_count)

xhs_search_synonym_dim = Table(
    "xhs_search_synonym_dim",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("term", String(255), nullable=False),
    Column("synonym", String(255), nullable=False),
    Column("lang", String(8), nullable=False, server_default="mixed"),
    Column("priority", Integer, nullable=False, server_default="100"),
    Column("status", String(20), nullable=False, server_default="enabled"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_search_synonym_dim_pair", xhs_search_synonym_dim.c.term, xhs_search_synonym_dim.c.synonym, unique=True)
Index("idx_xhs_search_synonym_dim_term", xhs_search_synonym_dim.c.term, xhs_search_synonym_dim.c.status)

xhs_note_search_result = Table(
    "xhs_note_search_result",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("batch_id", String(64), nullable=False),
    Column("task_id", String(128)),
    Column("keyword", String(255), nullable=False),
    Column("sort_type", String(32), nullable=False),
    Column("search_rank", Integer, nullable=False),
    Column("note_id", String(64), nullable=False),
    Column("title", Text),
    Column("author_nickname", String(255)),
    Column("post_url", Text),
    Column("publish_time", DateTime(timezone=True)),
    Column("search_date", Date, nullable=False, server_default=func.current_date()),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_note_search_result_daily", xhs_note_search_result.c.keyword, xhs_note_search_result.c.sort_type, xhs_note_search_result.c.note_id, xhs_note_search_result.c.search_date, unique=True)

xhs_category_dim = Table(
    "xhs_category_dim",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("platform", String(20), nullable=False, server_default="xhs"),
    Column("category_id", BigInteger, nullable=False),
    Column("category_name", String(100), nullable=False),
    Column("parent_category_id", BigInteger),
    Column("parent_category_name", String(100)),
    Column("level", Integer, nullable=False),
    Column("sort_no", Integer),
    Column("raw_payload", JSONB),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_category_dim_platform_category", xhs_category_dim.c.platform, xhs_category_dim.c.category_id, unique=True)
Index("idx_xhs_category_dim_parent", xhs_category_dim.c.parent_category_id)
Index("idx_xhs_category_dim_level", xhs_category_dim.c.level)

xhs_category_watchlist = Table(
    "xhs_category_watchlist",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("platform", String(20), nullable=False, server_default="xhs"),
    Column("industry_name", String(100), nullable=False),
    Column("category_id", BigInteger, nullable=False),
    Column("category_name", String(100), nullable=False),
    Column("parent_category_id", BigInteger),
    Column("parent_category_name", String(100)),
    Column("status", String(20), nullable=False, server_default="enabled"),
    Column("priority", Integer, nullable=False, server_default="100"),
    Column("remark", String(255)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_category_watchlist_platform_category", xhs_category_watchlist.c.platform, xhs_category_watchlist.c.category_id, unique=True)
Index("idx_xhs_category_watchlist_status", xhs_category_watchlist.c.status, xhs_category_watchlist.c.priority)

xhs_beauty_taxonomy_dim = Table(
    "xhs_beauty_taxonomy_dim",
    metadata,
    Column("category_name", String(100), primary_key=True),
    Column("sort_no", Integer, nullable=False),
    Column("status", String(20), nullable=False, server_default="enabled"),
    Column("keyword_count", Integer, nullable=False, server_default="0"),
    Column("keywords", ARRAY(Text), nullable=False, server_default="{}"),
    Column("remark", String(255)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("idx_xhs_beauty_taxonomy_dim_status", xhs_beauty_taxonomy_dim.c.status, xhs_beauty_taxonomy_dim.c.sort_no)

xhs_beauty_recommendation_dim = Table(
    "xhs_beauty_recommendation_dim",
    metadata,
    Column("group_name", String(100), primary_key=True),
    Column("sort_no", Integer, nullable=False),
    Column("status", String(20), nullable=False, server_default="enabled"),
    Column("keyword_count", Integer, nullable=False, server_default="0"),
    Column("keywords", ARRAY(Text), nullable=False, server_default="{}"),
    Column("remark", String(255)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("idx_xhs_beauty_recommendation_dim_status", xhs_beauty_recommendation_dim.c.status, xhs_beauty_recommendation_dim.c.sort_no)

xhs_anchor_dim = Table(
    "xhs_anchor_dim",
    metadata,
    Column("author_id", String(128), primary_key=True),
    Column("anchor_link", String(128)),
    Column("red_id", String(128)),
    Column("nickname", String(255)),
    Column("verified_type", String(255)),
    Column("user_text", Text),
    Column("user_sex", String(8)),
    Column("age", Integer),
    Column("fans_count", BigInteger),
    Column("follow_count", BigInteger),
    Column("fans_add_7", BigInteger),
    Column("fans_add_30", BigInteger),
    Column("fans_add_90", BigInteger),
    Column("note_add_7", BigInteger),
    Column("note_add_30", BigInteger),
    Column("note_add_90", BigInteger),
    Column("total_note_count", BigInteger),
    Column("like_coll_count", BigInteger),
    Column("picture_cpm", Numeric(18, 2)),
    Column("picture_cpe", Numeric(18, 2)),
    Column("picture_price", Numeric(18, 2)),
    Column("video_cpm", Numeric(18, 2)),
    Column("video_cpe", Numeric(18, 2)),
    Column("video_price", Numeric(18, 2)),
    Column("contact", String(255)),
    Column("tag_list", ARRAY(Text), nullable=False, server_default="{}"),
    Column("gender_distribution", JSONB),
    Column("age_distribution", JSONB),
    Column("city_distribution", JSONB),
    Column("province_distribution", JSONB),
    Column("interest_distribution", JSONB),
    Column("fans_active_day_distribution", JSONB),
    Column("fans_active_hour_distribution", JSONB),
    Column("fans_active_week_distribution", JSONB),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

xhs_fans_profile_snapshot = Table(
    "xhs_fans_profile_snapshot",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("author_id", String(128), nullable=False),
    Column("anchor_link", String(128)),
    Column("fans_count", BigInteger),
    Column("gender_distribution", JSONB),
    Column("age_distribution", JSONB),
    Column("city_distribution", JSONB),
    Column("province_distribution", JSONB),
    Column("interest_distribution", JSONB),
    Column("fans_active_day_distribution", JSONB),
    Column("fans_active_hour_distribution", JSONB),
    Column("fans_active_week_distribution", JSONB),
    Column("snapshot_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("idx_xhs_fans_profile_snapshot_author_time", xhs_fans_profile_snapshot.c.author_id, xhs_fans_profile_snapshot.c.snapshot_at)

xhs_comment_fact = Table(
    "xhs_comment_fact",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("parent_note_id", String(64), nullable=False),
    Column("comment_hash", String(64), nullable=False),
    Column("comment_text", Text, nullable=False),
    Column("sort_order", Integer),
    Column("commenter_id", String(128)),
    Column("commenter_nickname", String(255)),
    Column("comment_likes", BigInteger),
    Column("comment_time", DateTime(timezone=True)),
    Column("comment_sentiment", String(32)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_comment_fact_note_hash", xhs_comment_fact.c.parent_note_id, xhs_comment_fact.c.comment_hash, unique=True)

xhs_keyword_analysis = Table(
    "xhs_keyword_analysis",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("keyword", String(255), nullable=False),
    Column("last_days", Integer, nullable=False),
    Column("analysis_date", Date, nullable=False, server_default=func.current_date()),
    Column("cpm", Numeric(18, 4)),
    Column("cpe", Numeric(18, 4)),
    Column("note_num", BigInteger),
    Column("anchor_num", BigInteger),
    Column("read_total", BigInteger),
    Column("stat_total", BigInteger),
    Column("cost_total", Numeric(18, 2)),
    Column("like_coll_total", BigInteger),
    Column("brand_analysis", JSONB),
    Column("note_analysis", JSONB),
    Column("anchor_analysis", JSONB),
    Column("sentiment_analysis", JSONB),
    Column("read_analysis", JSONB),
    Column("raw_payload", JSONB),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_keyword_analysis_daily", xhs_keyword_analysis.c.keyword, xhs_keyword_analysis.c.last_days, xhs_keyword_analysis.c.analysis_date, unique=True)

xhs_brand_dim = Table(
    "xhs_brand_dim",
    metadata,
    Column("brand_id", String(128), primary_key=True),
    Column("brand_name", String(255), nullable=False),
    Column("alias", ARRAY(Text), nullable=False, server_default="{}"),
    Column("industry", String(255)),
    Column("description", Text),
    Column("raw_payload", JSONB),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("idx_xhs_brand_dim_name", xhs_brand_dim.c.brand_name)

xhs_note_brand_rel = Table(
    "xhs_note_brand_rel",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("note_id", String(64), nullable=False),
    Column("brand_id", String(128), nullable=False),
    Column("brand_name", String(255), nullable=False),
    Column("matched_keyword", String(255)),
    Column("match_source", String(32)),
    Column("match_position", Integer),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_note_brand_rel_note_brand", xhs_note_brand_rel.c.note_id, xhs_note_brand_rel.c.brand_id, unique=True)
Index("idx_xhs_note_brand_rel_brand", xhs_note_brand_rel.c.brand_name, xhs_note_brand_rel.c.note_id)

xhs_brand_account_rel = Table(
    "xhs_brand_account_rel",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("brand_id", String(128), nullable=False),
    Column("brand_name", String(255), nullable=False),
    Column("account_id", String(128), nullable=False),
    Column("account_name", String(255)),
    Column("account_type", String(64)),
    Column("platform", String(32), nullable=False, server_default="xhs"),
    Column("raw_payload", JSONB),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_brand_account_rel", xhs_brand_account_rel.c.brand_name, xhs_brand_account_rel.c.account_id, unique=True)

xhs_brand_analysis_snapshot = Table(
    "xhs_brand_analysis_snapshot",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("brand_name", String(255), nullable=False),
    Column("analysis_date", Date, nullable=False, server_default=func.current_date()),
    Column("brand_id", String(128)),
    Column("note_num", BigInteger),
    Column("anchor_num", BigInteger),
    Column("read_total", BigInteger),
    Column("stat_total", BigInteger),
    Column("cost_total", Numeric(18, 2)),
    Column("brand_analysis", JSONB),
    Column("raw_payload", JSONB),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_brand_analysis_daily", xhs_brand_analysis_snapshot.c.brand_name, xhs_brand_analysis_snapshot.c.analysis_date, unique=True)

# 任务治理层
xhs_crawl_log = Table(
    "xhs_crawl_log",
    metadata,
    Column("batch_id", String(64), primary_key=True),
    Column("task_type", String(64), nullable=False),
    Column("biz_type", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("keyword", String(255)),
    Column("note_id", String(64)),
    Column("author_id", String(128)),
    Column("brand_name", String(255)),
    Column("task_id", String(128)),
    Column("retry_count", Integer, nullable=False, server_default="0"),
    Column("request_payload", JSONB),
    Column("response_payload", JSONB),
    Column("callback_payload", JSONB),
    Column("row_count", Integer, nullable=False, server_default="0"),
    Column("error_msg", Text),
    Column("is_callback_received", Boolean, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
)
Index("idx_xhs_crawl_log_status", xhs_crawl_log.c.status)
Index("idx_xhs_crawl_log_task_type", xhs_crawl_log.c.task_type)
Index("idx_xhs_crawl_log_status_created_task", xhs_crawl_log.c.status, xhs_crawl_log.c.created_at, xhs_crawl_log.c.task_type)

xhs_search_job = Table(
    "xhs_search_job",
    metadata,
    Column("job_id", String(64), primary_key=True),
    Column("search_type", String(32), nullable=False),
    Column("query", String(255), nullable=False),
    Column("mode", String(32)),
    Column("industry_key", String(64)),
    Column("status", String(20), nullable=False, server_default="pending"),
    Column("crawl_batch_id", String(64)),
    Column("task_id", String(128)),
    Column("request_payload", JSONB),
    Column("response_payload", JSONB),
    Column("error_msg", Text),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
)
Index("idx_xhs_search_job_status", xhs_search_job.c.status, xhs_search_job.c.created_at)
Index("idx_xhs_search_job_query", xhs_search_job.c.search_type, xhs_search_job.c.query, xhs_search_job.c.created_at)

xhs_note_term_rel = Table(
    "xhs_note_term_rel",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("note_id", String(64), nullable=False),
    Column("term", String(255), nullable=False),
    Column("term_type", String(32), nullable=False, server_default="text"),
    Column("weight", Integer, nullable=False, server_default="1"),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("uq_xhs_note_term_rel_note_term_type", xhs_note_term_rel.c.note_id, xhs_note_term_rel.c.term, xhs_note_term_rel.c.term_type, unique=True)
Index("idx_xhs_note_term_rel_term_weight_time", xhs_note_term_rel.c.term, xhs_note_term_rel.c.weight, xhs_note_term_rel.c.updated_at)
Index("idx_xhs_note_term_rel_note_id", xhs_note_term_rel.c.note_id)

xhs_author_metrics_30d = Table(
    "xhs_author_metrics_30d",
    metadata,
    Column("author_id", String(128), primary_key=True),
    Column("author_nickname", String(255)),
    Column("note_count", BigInteger, nullable=False, server_default="0"),
    Column("interaction_total", BigInteger, nullable=False, server_default="0"),
    Column("like_total", BigInteger, nullable=False, server_default="0"),
    Column("comment_total", BigInteger, nullable=False, server_default="0"),
    Column("collection_total", BigInteger, nullable=False, server_default="0"),
    Column("share_total", BigInteger, nullable=False, server_default="0"),
    Column("note_max_fans", BigInteger, nullable=False, server_default="0"),
    Column("latest_data_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
Index("idx_xhs_author_metrics_30d_interaction_total", xhs_author_metrics_30d.c.interaction_total)
Index("idx_xhs_author_metrics_30d_latest_data_at", xhs_author_metrics_30d.c.latest_data_at)

xhs_note_change_log = Table(
    "xhs_note_change_log",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("note_id", String(64), nullable=False),
    Column("change_source", String(64), nullable=False, server_default="unknown"),
    Column("changed_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("processed_at", DateTime(timezone=True)),
)
Index("idx_xhs_note_change_log_processed_changed", xhs_note_change_log.c.processed_at, xhs_note_change_log.c.changed_at)
Index("idx_xhs_note_change_log_note_changed", xhs_note_change_log.c.note_id, xhs_note_change_log.c.changed_at)


def init_db() -> None:
    engine = create_engine(settings.sqlalchemy_url, echo=settings.db_echo)
    metadata.create_all(engine)
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:
            pass
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        except Exception:
            pass
        conn.execute(text("ALTER TABLE xhs_note_fact ADD COLUMN IF NOT EXISTS interaction_total bigint NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE xhs_note_fact ADD COLUMN IF NOT EXISTS ext_payload jsonb"))
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_xhs_note_change_log_pending_note
                ON xhs_note_change_log(note_id)
                WHERE processed_at IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE xhs_note_fact
                SET interaction_total =
                    COALESCE(like_count, 0)
                  + COALESCE(comment_count, 0)
                  + COALESCE(collection_count, 0)
                  + COALESCE(share_count, 0)
                WHERE COALESCE(interaction_total, 0) = 0
                """
            )
        )
        try:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_search_blob_trgm
                    ON xhs_note_fact
                    USING gin (
                        (
                            COALESCE(title, '')
                            || ' '
                            || COALESCE(content, '')
                            || ' '
                            || COALESCE(author_nickname, '')
                            || ' '
                            || COALESCE(search_keyword, '')
                        ) gin_trgm_ops
                    )
                    """
                )
            )
        except Exception:
            pass
        conn.execute(
            text(
                """
                INSERT INTO xhs_search_synonym_dim(term, synonym, lang, priority, status)
                VALUES
                    ('防晒', 'sunscreen', 'mixed', 10, 'enabled'),
                    ('sunscreen', '防晒', 'mixed', 10, 'enabled'),
                    ('口红', 'lipstick', 'mixed', 10, 'enabled'),
                    ('lipstick', '口红', 'mixed', 10, 'enabled'),
                    ('粉底', 'foundation', 'mixed', 20, 'enabled'),
                    ('foundation', '粉底', 'mixed', 20, 'enabled'),
                    ('精华', 'serum', 'mixed', 20, 'enabled'),
                    ('serum', '精华', 'mixed', 20, 'enabled'),
                    ('面膜', 'mask', 'mixed', 20, 'enabled'),
                    ('mask', '面膜', 'mixed', 20, 'enabled'),
                    ('美妆', 'beauty', 'mixed', 30, 'enabled'),
                    ('beauty', '美妆', 'mixed', 30, 'enabled')
                ON CONFLICT (term, synonym) DO UPDATE SET
                    status = EXCLUDED.status,
                    priority = LEAST(xhs_search_synonym_dim.priority, EXCLUDED.priority),
                    updated_at = now()
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE VIEW xhs_note_center_view AS
                SELECT
                    'xiaohongshu'::text AS platform,
                    f.search_keyword,
                    f.search_rank,
                    f.search_type,
                    f.note_id,
                    'https://www.xiaohongshu.com/explore/' || f.note_id AS post_url,
                    COALESCE(f.publish_time, f.created_at) AS publish_time,
                    f.title,
                    COALESCE(f.content, '') AS content,
                    f.media_type,
                    COALESCE(f.tags, ARRAY[]::text[]) AS tags,
                    f.media_urls,
                    f.cover_image_url,
                    COALESCE(f.like_count, 0) AS like_count,
                    COALESCE(f.collection_count, 0) AS collection_count,
                    COALESCE(f.comment_count, 0) AS comment_count,
                    COALESCE(f.share_count, 0) AS share_count,
                    COALESCE(f.read_count, 0) AS read_count,
                    COALESCE(a.author_id, f.author_id) AS author_id,
                    COALESCE(a.nickname, f.author_nickname) AS nickname,
                    COALESCE(a.fans_count, f.author_fans_count, 0) AS follower_count,
                    a.verified_type,
                    a.video_cpm,
                    a.picture_cpm,
                    a.total_note_count AS total_notes,
                    a.like_coll_count AS like_coll_total,
                    COALESCE(f.updated_at, f.created_at) AS crawl_time
                FROM xhs_note_fact f
                LEFT JOIN xhs_anchor_dim a
                  ON a.author_id = f.author_id
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE VIEW xhs_comment_center_view AS
                SELECT
                    parent_note_id,
                    comment_text,
                    comment_sentiment,
                    commenter_id,
                    commenter_nickname,
                    comment_likes,
                    comment_time,
                    created_at AS crawl_time
                FROM xhs_comment_fact
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE VIEW xhs_anchor_center_view AS
                SELECT
                    author_id,
                    nickname,
                    fans_count AS follower_count,
                    verified_type,
                    video_cpm,
                    picture_cpm,
                    total_note_count AS total_notes,
                    like_coll_count AS like_coll_total,
                    updated_at AS crawl_time,
                    anchor_link,
                    red_id,
                    contact
                FROM xhs_anchor_dim
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE VIEW xhs_brand_center_view AS
                SELECT
                    rel.brand_id,
                    rel.brand_name,
                    COUNT(DISTINCT rel.note_id) AS note_count,
                    COUNT(DISTINCT f.author_id) AS creator_count,
                    COALESCE(SUM(f.like_count), 0) AS like_total,
                    COALESCE(SUM(f.collection_count), 0) AS collection_total,
                    COALESCE(SUM(f.comment_count), 0) AS comment_total,
                    COALESCE(SUM(f.read_count), 0) AS read_total,
                    COALESCE(MAX(f.like_count), 0) AS max_like_count,
                    MAX(COALESCE(f.publish_time, f.created_at)) AS latest_publish_time,
                    MAX(rel.updated_at) AS crawl_time
                FROM xhs_note_brand_rel rel
                JOIN xhs_note_fact f
                  ON f.note_id = rel.note_id
                GROUP BY rel.brand_id, rel.brand_name
                """
            )
        )
    print("database initialized")


if __name__ == "__main__":
    init_db()
