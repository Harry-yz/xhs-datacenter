from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "xhs-data-center")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_public_base_url: str = os.getenv("APP_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    auth_session_secret: str = os.getenv("AUTH_SESSION_SECRET", os.getenv("HUITUN_SECRET_KEY", "dev-secret-change-me"))
    auth_session_ttl_hours: int = int(os.getenv("AUTH_SESSION_TTL_HOURS", "168"))
    auth_admin_email: str = os.getenv("AUTH_ADMIN_EMAIL", "")
    auth_admin_password: str = os.getenv("AUTH_ADMIN_PASSWORD", "")

    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "data_center_1")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "postgres")
    db_echo: bool = _get_bool("DB_ECHO", False)

    huitun_base_url: str = os.getenv("HUITUN_BASE_URL", "https://dataapi.huitun.com")
    huitun_client_id: str = os.getenv("HUITUN_CLIENT_ID", "")
    huitun_secret_key: str = os.getenv("HUITUN_SECRET_KEY", "")
    huitun_platform: str = os.getenv("HUITUN_PLATFORM", "xhs")
    huitun_verify_ssl: bool = _get_bool("HUITUN_VERIFY_SSL", False)

    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")
    task_default_queue: str = os.getenv("TASK_DEFAULT_QUEUE", "xhs_queue")
    task_priority_queue: str = os.getenv("TASK_PRIORITY_QUEUE", "xhs_priority_queue")
    celery_worker_concurrency: int = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
    huitun_note_info_rate_limit: str = os.getenv("HUITUN_NOTE_INFO_RATE_LIMIT", "30/m")
    huitun_note_search_rate_limit: str = os.getenv("HUITUN_NOTE_SEARCH_RATE_LIMIT", "150/m")
    huitun_note_comment_rate_limit: str = os.getenv("HUITUN_NOTE_COMMENT_RATE_LIMIT", "18/m")
    huitun_anchor_info_rate_limit: str = os.getenv("HUITUN_ANCHOR_INFO_RATE_LIMIT", "12/m")
    huitun_fans_portrait_rate_limit: str = os.getenv("HUITUN_FANS_PORTRAIT_RATE_LIMIT", "6/m")
    huitun_task_retry_delay_seconds: int = int(os.getenv("HUITUN_TASK_RETRY_DELAY_SECONDS", "180"))
    huitun_auto_note_info_spacing_seconds: int = int(os.getenv("HUITUN_AUTO_NOTE_INFO_SPACING_SECONDS", "2"))
    huitun_auto_note_comment_spacing_seconds: int = int(os.getenv("HUITUN_AUTO_NOTE_COMMENT_SPACING_SECONDS", "4"))
    beauty_scheduler_interval_minutes: int = int(os.getenv("BEAUTY_SCHEDULER_INTERVAL_MINUTES", "1440"))
    beauty_scheduler_keyword_batch_size: int = int(os.getenv("BEAUTY_SCHEDULER_KEYWORD_BATCH_SIZE", "98"))
    beauty_scheduler_search_limit: int = int(os.getenv("BEAUTY_SCHEDULER_SEARCH_LIMIT", "300"))
    beauty_scheduler_note_info_limit: int = int(os.getenv("BEAUTY_SCHEDULER_NOTE_INFO_LIMIT", "12"))
    beauty_scheduler_note_comment_limit: int = int(os.getenv("BEAUTY_SCHEDULER_NOTE_COMMENT_LIMIT", "3"))
    beauty_scheduler_anchor_limit: int = int(os.getenv("BEAUTY_SCHEDULER_ANCHOR_LIMIT", "2"))
    beauty_scheduler_fans_limit: int = int(os.getenv("BEAUTY_SCHEDULER_FANS_LIMIT", "0"))
    beauty_scheduler_recent_hours: int = int(os.getenv("BEAUTY_SCHEDULER_RECENT_HOURS", "24"))
    beauty_scheduler_nickname_anchor_limit: int = int(os.getenv("BEAUTY_SCHEDULER_NICKNAME_ANCHOR_LIMIT", "100"))
    beauty_scheduler_nickname_anchor_spacing_seconds: float = float(os.getenv("BEAUTY_SCHEDULER_NICKNAME_ANCHOR_SPACING_SECONDS", "1.5"))
    beauty_scheduler_search_sorts: str = os.getenv("BEAUTY_SCHEDULER_SEARCH_SORTS", "1,0")
    industry_scheduler_interval_minutes: int = int(os.getenv("INDUSTRY_SCHEDULER_INTERVAL_MINUTES", os.getenv("BEAUTY_SCHEDULER_INTERVAL_MINUTES", "1440")))
    industry_scheduler_keyword_batch_size: int = int(os.getenv("INDUSTRY_SCHEDULER_KEYWORD_BATCH_SIZE", os.getenv("BEAUTY_SCHEDULER_KEYWORD_BATCH_SIZE", "120")))
    industry_scheduler_search_limit: int = int(os.getenv("INDUSTRY_SCHEDULER_SEARCH_LIMIT", os.getenv("BEAUTY_SCHEDULER_SEARCH_LIMIT", "420")))
    industry_scheduler_note_info_limit: int = int(os.getenv("INDUSTRY_SCHEDULER_NOTE_INFO_LIMIT", os.getenv("BEAUTY_SCHEDULER_NOTE_INFO_LIMIT", "420")))
    industry_scheduler_note_comment_limit: int = int(os.getenv("INDUSTRY_SCHEDULER_NOTE_COMMENT_LIMIT", os.getenv("BEAUTY_SCHEDULER_NOTE_COMMENT_LIMIT", "120")))
    industry_scheduler_anchor_limit: int = int(os.getenv("INDUSTRY_SCHEDULER_ANCHOR_LIMIT", os.getenv("BEAUTY_SCHEDULER_ANCHOR_LIMIT", "80")))
    industry_scheduler_fans_limit: int = int(os.getenv("INDUSTRY_SCHEDULER_FANS_LIMIT", os.getenv("BEAUTY_SCHEDULER_FANS_LIMIT", "0")))
    industry_scheduler_recent_hours: int = int(os.getenv("INDUSTRY_SCHEDULER_RECENT_HOURS", os.getenv("BEAUTY_SCHEDULER_RECENT_HOURS", "24")))
    industry_scheduler_nickname_anchor_limit: int = int(os.getenv("INDUSTRY_SCHEDULER_NICKNAME_ANCHOR_LIMIT", os.getenv("BEAUTY_SCHEDULER_NICKNAME_ANCHOR_LIMIT", "150")))
    industry_scheduler_nickname_anchor_spacing_seconds: float = float(os.getenv("INDUSTRY_SCHEDULER_NICKNAME_ANCHOR_SPACING_SECONDS", os.getenv("BEAUTY_SCHEDULER_NICKNAME_ANCHOR_SPACING_SECONDS", "1.2")))
    industry_scheduler_search_sorts: str = os.getenv("INDUSTRY_SCHEDULER_SEARCH_SORTS", os.getenv("BEAUTY_SCHEDULER_SEARCH_SORTS", "1,0"))
    industry_scheduler_adaptive_window_minutes: int = int(os.getenv("INDUSTRY_SCHEDULER_ADAPTIVE_WINDOW_MINUTES", "30"))
    industry_scheduler_boost_multiplier: float = float(os.getenv("INDUSTRY_SCHEDULER_BOOST_MULTIPLIER", "1.35"))
    industry_scheduler_backoff_multiplier: float = float(os.getenv("INDUSTRY_SCHEDULER_BACKOFF_MULTIPLIER", "0.6"))
    industry_scheduler_backoff_fail_ratio_threshold: float = float(
        os.getenv("INDUSTRY_SCHEDULER_BACKOFF_FAIL_RATIO_THRESHOLD", "0.35")
    )
    industry_scheduler_backoff_rate_limit_threshold: int = int(
        os.getenv("INDUSTRY_SCHEDULER_BACKOFF_RATE_LIMIT_THRESHOLD", "12")
    )
    industry_scheduler_boost_fail_ratio_threshold: float = float(
        os.getenv("INDUSTRY_SCHEDULER_BOOST_FAIL_RATIO_THRESHOLD", "0.03")
    )
    industry_scheduler_boost_rate_limit_threshold: int = int(
        os.getenv("INDUSTRY_SCHEDULER_BOOST_RATE_LIMIT_THRESHOLD", "1")
    )
    industry_classify_backfill_batch_size: int = int(os.getenv("INDUSTRY_CLASSIFY_BACKFILL_BATCH_SIZE", "1200"))
    industry_classify_backfill_shards: int = int(os.getenv("INDUSTRY_CLASSIFY_BACKFILL_SHARDS", "1"))
    industry_classify_backfill_shard_index: int = int(os.getenv("INDUSTRY_CLASSIFY_BACKFILL_SHARD_INDEX", "0"))
    industry_classify_backfill_workers: int = int(os.getenv("INDUSTRY_CLASSIFY_BACKFILL_WORKERS", "1"))
    search_min_healthy_results: int = int(os.getenv("SEARCH_MIN_HEALTHY_RESULTS", "20"))
    search_stale_hours: int = int(os.getenv("SEARCH_STALE_HOURS", "24"))
    search_coalesce_lock_ttl_seconds: int = int(os.getenv("SEARCH_COALESCE_LOCK_TTL_SECONDS", "20"))
    search_coalesce_job_ttl_seconds: int = int(os.getenv("SEARCH_COALESCE_JOB_TTL_SECONDS", "180"))
    search_coalesce_wait_ms: int = int(os.getenv("SEARCH_COALESCE_WAIT_MS", "900"))
    search_author_backfill_cooldown_hours: int = int(os.getenv("SEARCH_AUTHOR_BACKFILL_COOLDOWN_HOURS", "12"))
    search_author_backfill_limit: int = int(os.getenv("SEARCH_AUTHOR_BACKFILL_LIMIT", "30"))
    search_creator_note_backfill_cooldown_hours: int = int(
        os.getenv("SEARCH_CREATOR_NOTE_BACKFILL_COOLDOWN_HOURS", "12")
    )
    search_creator_note_backfill_limit: int = int(os.getenv("SEARCH_CREATOR_NOTE_BACKFILL_LIMIT", "8"))
    search_creator_note_backfill_note_count_threshold: int = int(
        os.getenv("SEARCH_CREATOR_NOTE_BACKFILL_NOTE_COUNT_THRESHOLD", "2")
    )
    search_creator_note_backfill_max_items: int = int(os.getenv("SEARCH_CREATOR_NOTE_BACKFILL_MAX_ITEMS", "120"))
    crawl_running_timeout_minutes: int = int(os.getenv("CRAWL_RUNNING_TIMEOUT_MINUTES", "90"))

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
