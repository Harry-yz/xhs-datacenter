from __future__ import annotations

import argparse
import time

from sqlalchemy import text

from app.db import SessionLocal
from app.services.huitun_client import HuitunClient

client = HuitunClient()


def _pick_candidate(nickname: str, items: list[dict]) -> dict | None:
    nickname_norm = nickname.strip().lower()
    exact = [
        item for item in items
        if str(item.get("nick") or "").strip().lower() == nickname_norm
    ]
    if exact:
        return exact[0]
    if len(items) == 1:
        return items[0]
    return None


def main(limit: int = 100, min_like: int = 100, spacing_seconds: float = 1.5) -> int:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT author_nickname
                FROM xhs_note_fact
                WHERE COALESCE(like_count, 0) >= :min_like
                  AND COALESCE(author_id, '') = ''
                  AND COALESCE(author_nickname, '') <> ''
                GROUP BY author_nickname
                ORDER BY MAX(COALESCE(like_count, 0)) DESC, COUNT(*) DESC, author_nickname ASC
                LIMIT :limit
                """
            ),
            {"limit": limit, "min_like": min_like},
        ).scalars().all()

        matched = 0
        for index, nickname in enumerate(rows, start=1):
            resp = client.search_anchors(keyword=nickname)
            items = resp.get("data") or []
            if not isinstance(items, list):
                items = []

            candidate = _pick_candidate(nickname, items)
            if not candidate:
                print(f"skip_nickname={nickname}")
                time.sleep(spacing_seconds)
                continue

            author_id = str(candidate.get("anchorId") or "").strip()
            if not author_id:
                print(f"skip_anchor_id_missing nickname={nickname}")
                time.sleep(spacing_seconds)
                continue

            fans_count = candidate.get("fans") or candidate.get("fansCount")
            total_note_count = candidate.get("note") or candidate.get("totalNoteCount")

            db.execute(
                text(
                    """
                    INSERT INTO xhs_anchor_dim(author_id, nickname, fans_count, total_note_count)
                    VALUES(:author_id, :nickname, :fans_count, :total_note_count)
                    ON CONFLICT(author_id) DO UPDATE SET
                        nickname = COALESCE(EXCLUDED.nickname, xhs_anchor_dim.nickname),
                        fans_count = COALESCE(EXCLUDED.fans_count, xhs_anchor_dim.fans_count),
                        total_note_count = COALESCE(EXCLUDED.total_note_count, xhs_anchor_dim.total_note_count),
                        updated_at = now()
                    """
                ),
                {
                    "author_id": author_id,
                    "nickname": nickname,
                    "fans_count": fans_count,
                    "total_note_count": total_note_count,
                },
            )

            updated = db.execute(
                text(
                    """
                    UPDATE xhs_note_fact
                    SET author_id = :author_id,
                        author_fans_count = COALESCE(author_fans_count, :fans_count),
                        updated_at = now()
                    WHERE COALESCE(author_id, '') = ''
                      AND author_nickname = :nickname
                      AND COALESCE(like_count, 0) >= :min_like
                    """
                ),
                {
                    "author_id": author_id,
                    "fans_count": fans_count,
                    "nickname": nickname,
                    "min_like": min_like,
                },
            ).rowcount

            db.commit()
            matched += 1
            print(
                f"{index}. nickname={nickname} author_id={author_id} "
                f"fans_count={fans_count} updated_notes={updated}"
            )
            time.sleep(spacing_seconds)

        return matched
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-like", type=int, default=100)
    parser.add_argument("--spacing-seconds", type=float, default=1.5)
    args = parser.parse_args()
    print(
        f"matched_count={main(limit=args.limit, min_like=args.min_like, spacing_seconds=args.spacing_seconds)}"
    )
