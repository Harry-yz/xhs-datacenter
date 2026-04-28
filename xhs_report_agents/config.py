from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _load_env() -> None:
    if load_dotenv is None:
        return
    load_dotenv(PROJECT_DIR / ".env")
    load_dotenv(BASE_DIR / ".env")


_load_env()


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str
    output_dir: Path
    deepseek_fast_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    request_timeout_seconds: int = 90
    llm_max_retries: int = 2


def _database_url() -> str:
    explicit = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL")
    if explicit:
        return explicit
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "data_center")
    user = os.getenv("DB_USER", "postgres")
    password = quote_plus(os.getenv("DB_PASSWORD", "postgres"))
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def get_settings(output_dir: str | None = None, *, require_llm_key: bool = True) -> Settings:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if require_llm_key and not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required")
    return Settings(
        deepseek_api_key=api_key,
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        deepseek_fast_model=os.getenv("DEEPSEEK_FAST_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")),
        deepseek_pro_model=os.getenv("DEEPSEEK_PRO_MODEL", "deepseek-v4-pro"),
        database_url=_database_url(),
        output_dir=Path(output_dir).resolve() if output_dir else BASE_DIR / "outputs",
        request_timeout_seconds=int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "90")),
        llm_max_retries=int(os.getenv("DEEPSEEK_MAX_RETRIES", "2")),
    )
