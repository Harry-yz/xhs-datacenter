from __future__ import annotations

import argparse
import hashlib
import json
import time
from typing import Any

import requests
import urllib3
from sqlalchemy import text
from sqlalchemy.orm import Session
from urllib3.exceptions import InsecureRequestWarning

from app.config import get_settings
from app.db import SessionLocal
from app.services.beauty_taxonomy import BEAUTY_KEYWORDS, BEAUTY_TAXONOMY
from app.services.ingest import create_crawl_log, save_search_results
from app.services.huitun_client import HuitunClient

settings = get_settings()
if not settings.huitun_verify_ssl:
    urllib3.disable_warnings(InsecureRequestWarning)
client = HuitunClient()

BEAUTY_CATEGORY_NAMES = list(BEAUTY_TAXONOMY.keys())

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "xhs-data-center/1.0",
}


def _db() -> Session:
    return SessionLocal()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _sign(params: dict[str, Any], secret_key: str) -> str:
    items: list[tuple[str, str]] = []
    for key in sorted(params.keys()):
        value = params[key]
        if value is None or value == "":
            continue
        if isinstance(value, list):
            value_str = ",".join(str(v) for v in value)
        elif isinstance(value, dict):
            value_str = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            value_str = str(value)
        items.append((key, value_str))
    raw = "&".join(f"{k}={v}" for k, v in items) + f"&secretKey={secret_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def _post(path: str, payload: dict[str, Any], include_platform: bool = True) -> dict[str, Any]:
    url = f"{settings.huitun_base_url.rstrip('/')}{path}"
    req = dict(payload)
    req["clientId"] = settings.huitun_client_id
    req["timestamp"] = int(time.time() * 1000)

    if include_platform:
        req["platform"] = getattr(settings, "huitun_platform", "xhs")

    req["sign"] = _sign(req, settings.huitun_secret_key)

    resp = requests.post(
        url,
        headers=HEADERS,
        data=json.dumps(req, ensure_ascii=False),
        timeout=60,
        verify=settings.huitun_verify_ssl,
    )
    resp.raise_for_status()
    data = resp.json()
    return data


def sync_categories() -> int:
    db = _db()
    try:
        batch_id = f"cat_{int(time.time())}"
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_category_sync",
            biz_type="sync",
            status="running",
            request_payload={},
            response_payload={"message": "category sync started"},
        )
        db.commit()

        data = _post("/api/v1/cg/noteTag", {}, include_platform=False)
        rows = 0

        for top_idx, parent in enumerate(_as_list(data.get("data")), start=1):
            parent_id = int(parent.get("tagId"))
            parent_name = str(parent.get("label") or "").strip()
            sub_list = _as_list(parent.get("subTagList"))

            db.execute(
                text(
                    """
                    INSERT INTO xhs_category_dim(
                        platform, category_id, category_name, parent_category_id,
                        parent_category_name, level, sort_no, raw_payload
                    )
                    VALUES(
                        'xhs', :category_id, :category_name, NULL,
                        NULL, 1, :sort_no, CAST(:raw_payload AS jsonb)
                    )
                    ON CONFLICT(platform, category_id) DO UPDATE SET
                        category_name = EXCLUDED.category_name,
                        sort_no = EXCLUDED.sort_no,
                        raw_payload = EXCLUDED.raw_payload,
                        updated_at = now()
                    """
                ),
                {
                    "category_id": parent_id,
                    "category_name": parent_name,
                    "sort_no": top_idx,
                    "raw_payload": json.dumps(parent, ensure_ascii=False),
                },
            )
            rows += 1

            for sub_idx, child in enumerate(sub_list, start=1):
                child_id = int(child.get("tagId"))
                child_name = str(child.get("label") or "").strip()

                db.execute(
                    text(
                        """
                        INSERT INTO xhs_category_dim(
                            platform, category_id, category_name, parent_category_id,
                            parent_category_name, level, sort_no, raw_payload
                        )
                        VALUES(
                            'xhs', :category_id, :category_name, :parent_category_id,
                            :parent_category_name, 2, :sort_no, CAST(:raw_payload AS jsonb)
                        )
                        ON CONFLICT(platform, category_id) DO UPDATE SET
                            category_name = EXCLUDED.category_name,
                            parent_category_id = EXCLUDED.parent_category_id,
                            parent_category_name = EXCLUDED.parent_category_name,
                            sort_no = EXCLUDED.sort_no,
                            raw_payload = EXCLUDED.raw_payload,
                            updated_at = now()
                        """
                    ),
                    {
                        "category_id": child_id,
                        "category_name": child_name,
                        "parent_category_id": parent_id,
                        "parent_category_name": parent_name,
                        "sort_no": sub_idx,
                        "raw_payload": json.dumps(child, ensure_ascii=False),
                    },
                )
                rows += 1

        db.execute(
            text(
                """
                UPDATE xhs_crawl_log
                SET status = 'success',
                    row_count = :row_count,
                    response_payload = CAST(:response_payload AS jsonb),
                    completed_at = now(),
                    updated_at = now()
                WHERE batch_id = :batch_id
                """
            ),
            {
                "batch_id": batch_id,
                "row_count": rows,
                "response_payload": json.dumps(data, ensure_ascii=False),
            },
        )
        db.commit()
        return rows
    finally:
        db.close()


def seed_beauty_watchlist() -> int:
    db = _db()
    try:
        rows = db.execute(
            text(
                """
                SELECT category_id, category_name, parent_category_id, parent_category_name
                FROM xhs_category_dim
                WHERE platform = 'xhs'
                  AND level = 2
                  AND category_name = ANY(:names)
                ORDER BY category_name
                """
            ),
            {"names": BEAUTY_CATEGORY_NAMES},
        ).mappings().all()

        inserted = 0
        for row in rows:
            db.execute(
                text(
                    """
                    INSERT INTO xhs_category_watchlist(
                        platform, industry_name, category_id, category_name,
                        parent_category_id, parent_category_name, status, priority, remark
                    )
                    VALUES(
                        'xhs', '美妆', :category_id, :category_name,
                        :parent_category_id, :parent_category_name, 'enabled', 10, '美妆核心品类'
                    )
                    ON CONFLICT(platform, category_id) DO UPDATE SET
                        industry_name = EXCLUDED.industry_name,
                        category_name = EXCLUDED.category_name,
                        parent_category_id = EXCLUDED.parent_category_id,
                        parent_category_name = EXCLUDED.parent_category_name,
                        status = EXCLUDED.status,
                        priority = EXCLUDED.priority,
                        remark = EXCLUDED.remark,
                        updated_at = now()
                    """
                ),
                dict(row),
            )
            inserted += 1

        db.commit()
        return inserted
    finally:
        db.close()


def crawl_watchlist(limit_per_category: int = 20) -> int:
    db = _db()
    try:
        watchlist = db.execute(
            text(
                """
                SELECT category_id, category_name, priority
                FROM xhs_category_watchlist
                WHERE platform = 'xhs' AND status = 'enabled'
                ORDER BY priority ASC, id ASC
                """
            )
        ).mappings().all()

        total_rows = 0

        for row in watchlist:
            category_id = int(row["category_id"])
            category_name = str(row["category_name"])

            for sort in (1, 0):
                batch_id = f"{category_id}_{sort}_{int(time.time())}"

                create_crawl_log(
                    db,
                    batch_id=batch_id,
                    task_type="note_search",
                    biz_type="category_crawl",
                    status="running",
                    keyword=category_name,
                    request_payload={
                        "category_id": category_id,
                        "category_name": category_name,
                        "sort": sort,
                        "limit": limit_per_category,
                    },
                    response_payload={"message": "category crawl started"},
                )
                db.commit()

                response = _post(
                    "/api/v1/cg/note/search",
                    {
                        "tagList": [category_id],
                        "sort": sort,
                    },
                )
                items = _as_list(response.get("data"))[:limit_per_category]

                row_count = save_search_results(
                    db,
                    keyword=category_name,
                    sort=sort,
                    results=items,
                    batch_id=batch_id,
                    task_id=None,
                )

                db.execute(
                    text(
                        """
                        UPDATE xhs_crawl_log
                        SET status = 'success',
                            row_count = :row_count,
                            response_payload = CAST(:response_payload AS jsonb),
                            completed_at = now(),
                            updated_at = now()
                        WHERE batch_id = :batch_id
                        """
                    ),
                    {
                        "batch_id": batch_id,
                        "row_count": row_count,
                        "response_payload": json.dumps(response, ensure_ascii=False),
                    },
                )
                db.commit()
                total_rows += row_count
                time.sleep(1)

        return total_rows
    finally:
        db.close()


def crawl_keywords(limit_per_keyword: int = 100, sort: int = 1) -> int:
    return crawl_keywords_for_list(BEAUTY_KEYWORDS, limit_per_keyword=limit_per_keyword, sort=sort)


def crawl_keywords_for_list(
    keywords: list[str],
    limit_per_keyword: int = 100,
    sort: int = 1,
    biz_type: str = "beauty_keyword_crawl",
) -> int:
    db = _db()
    try:
        total_rows = 0

        for keyword in keywords:
            batch_id = f"kw_{hashlib.md5(f'{keyword}_{sort}_{time.time()}'.encode('utf-8')).hexdigest()[:16]}"

            create_crawl_log(
                db,
                batch_id=batch_id,
                task_type="note_search",
                biz_type=biz_type,
                status="running",
                keyword=keyword,
                request_payload={
                    "keyword": keyword,
                    "sort": sort,
                    "limit": limit_per_keyword,
                },
                response_payload={"message": "beauty keyword crawl started"},
            )
            db.commit()

            response = client.search_notes(keyword=keyword, sort=sort)
            items = _as_list(response.get("data"))[:limit_per_keyword]

            row_count = save_search_results(
                db,
                keyword=keyword,
                sort=sort,
                results=items,
                batch_id=batch_id,
                task_id=None,
            )

            db.execute(
                text(
                    """
                    UPDATE xhs_crawl_log
                    SET status = 'success',
                        row_count = :row_count,
                        response_payload = CAST(:response_payload AS jsonb),
                        completed_at = now(),
                        updated_at = now()
                    WHERE batch_id = :batch_id
                    """
                ),
                {
                    "batch_id": batch_id,
                    "row_count": row_count,
                    "response_payload": json.dumps(response, ensure_ascii=False),
                },
            )
            db.commit()
            total_rows += row_count
            time.sleep(1)

        return total_rows
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["sync_categories", "seed_watchlist", "crawl_watchlist", "crawl_keywords"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.action == "sync_categories":
        print(f"[OK] synced categories: {sync_categories()}")
    elif args.action == "seed_watchlist":
        print(f"[OK] seeded beauty watchlist: {seed_beauty_watchlist()}")
    elif args.action == "crawl_watchlist":
        print(f"[OK] crawled watchlist notes: {crawl_watchlist(limit_per_category=args.limit)}")
    elif args.action == "crawl_keywords":
        print(f"[OK] crawled beauty keyword notes: {crawl_keywords(limit_per_keyword=args.limit)}")


if __name__ == "__main__":
    main()
