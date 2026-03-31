from __future__ import annotations


def _is_profile_url(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if not text.startswith("http"):
        return False
    return "xiaohongshu.com/user/profile/" in text


def resolve_anchor_link(anchor_ref: str | None, stored_anchor_link: str | None = None) -> str | None:
    if _is_profile_url(anchor_ref):
        return anchor_ref.strip()
    if _is_profile_url(stored_anchor_link):
        return stored_anchor_link.strip()
    return None


def resolve_author_id(author_ref: str | None, stored_author_id: str | None = None) -> str | None:
    for value in (author_ref, stored_author_id):
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
