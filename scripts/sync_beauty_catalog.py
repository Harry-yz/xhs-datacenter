from __future__ import annotations

from app.db import SessionLocal
from app.services.beauty_catalog import sync_beauty_catalog


def main() -> None:
    db = SessionLocal()
    try:
        result = sync_beauty_catalog(db)
        print(
            "[OK] synced beauty catalog: "
            f"categories={result['category_count']} "
            f"keywords={result['keyword_count']} "
            f"recommended_groups={result['recommended_expansion_group_count']} "
            f"recommended_keywords={result['recommended_keyword_count']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
