from __future__ import annotations

from sqlalchemy import text

from app.db import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        statements = [
            "CREATE EXTENSION IF NOT EXISTS pg_trgm",
            "CREATE EXTENSION IF NOT EXISTS unaccent",
            "ALTER TABLE xhs_note_fact ADD COLUMN IF NOT EXISTS interaction_total bigint NOT NULL DEFAULT 0",
            "ALTER TABLE xhs_note_fact ADD COLUMN IF NOT EXISTS ext_payload jsonb",
            """
            UPDATE xhs_note_fact
            SET interaction_total =
                COALESCE(like_count, 0)
              + COALESCE(comment_count, 0)
              + COALESCE(collection_count, 0)
              + COALESCE(share_count, 0)
            WHERE COALESCE(interaction_total, 0) = 0
               OR interaction_total <> (
                    COALESCE(like_count, 0)
                  + COALESCE(comment_count, 0)
                  + COALESCE(collection_count, 0)
                  + COALESCE(share_count, 0)
               )
            """,
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_interaction_total ON xhs_note_fact(interaction_total DESC)",
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_like_count ON xhs_note_fact(like_count DESC)",
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_comment_count ON xhs_note_fact(comment_count DESC)",
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_collection_count ON xhs_note_fact(collection_count DESC)",
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_read_count ON xhs_note_fact(read_count DESC)",
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
            """,
            """
            CREATE TABLE IF NOT EXISTS xhs_search_synonym_dim (
                id bigserial PRIMARY KEY,
                term varchar(255) NOT NULL,
                synonym varchar(255) NOT NULL,
                lang varchar(8) NOT NULL DEFAULT 'mixed',
                priority integer NOT NULL DEFAULT 100,
                status varchar(20) NOT NULL DEFAULT 'enabled',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_xhs_search_synonym_dim_pair ON xhs_search_synonym_dim(term, synonym)",
            "CREATE INDEX IF NOT EXISTS idx_xhs_search_synonym_dim_term ON xhs_search_synonym_dim(term, status)",
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
                ('mask', '面膜', 'mixed', 20, 'enabled')
            ON CONFLICT (term, synonym) DO UPDATE SET
                status = EXCLUDED.status,
                priority = LEAST(xhs_search_synonym_dim.priority, EXCLUDED.priority),
                updated_at = now()
            """,
        ]

        for sql in statements:
            try:
                db.execute(text(sql))
                db.commit()
            except Exception as exc:
                message = str(exc).lower()
                if (
                    "permission denied" in message
                    or "must have create privilege" in message
                    or "must be superuser" in message
                    or ("gin_trgm_ops" in message and "does not exist" in message)
                ):
                    db.rollback()
                    continue
                raise
        print("migration completed: search_engine_v2")
    finally:
        db.close()


if __name__ == "__main__":
    main()
