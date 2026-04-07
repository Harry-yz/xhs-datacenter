from __future__ import annotations

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=max(1, settings.db_pool_size),
    max_overflow=max(0, settings.db_max_overflow),
    pool_timeout=max(5, settings.db_pool_timeout_seconds),
    pool_recycle=max(300, settings.db_pool_recycle_seconds),
    pool_use_lifo=True,
    connect_args={"connect_timeout": max(3, settings.db_connect_timeout_seconds)},
    echo=settings.db_echo,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
