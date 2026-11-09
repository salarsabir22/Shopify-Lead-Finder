"""Local file-based lead memory — no database required."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from config import OUTPUT_DIR
from email_utils import clean_email

SEEN_FILE = Path(OUTPUT_DIR) / "seen_leads.json"


def _norm_host(url: str) -> str:
    if not url:
        return ""
    raw = url.strip().lower()
    if "://" not in raw:
        raw = "https://" + raw
    return (urlparse(raw).hostname or "").lower().removeprefix("www.")


def load_seen() -> dict:
    if not SEEN_FILE.exists():
        return {"urls": [], "emails": []}
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"urls": [], "emails": []}
    return {
        "urls": list(data.get("urls") or []),
        "emails": list(data.get("emails") or []),
    }


def seen_sets() -> tuple[set[str], set[str]]:
    data = load_seen()
    urls = {_norm_host(u) for u in data["urls"] if _norm_host(u)}
    emails = {clean_email(e) or "" for e in data["emails"]}
    emails.discard("")
    return urls, emails


def store_keys(store: dict) -> set[str]:
    keys: set[str] = set()
    for field in ("url", "custom_domain", "myshopify_url", "store_url"):
        host = _norm_host(store.get(field) or "")
        if host:
            keys.add(host)
    return keys


def filter_new_stores(stores: list[dict], seen_urls: set[str]) -> list[dict]:
    out: list[dict] = []
    batch_seen: set[str] = set()
    for store in stores:
        keys = store_keys(store)
        if not keys:
            continue
        if keys & seen_urls or keys & batch_seen:
            continue
        batch_seen |= keys
        out.append(store)
    return out


def remember_leads(leads: list[dict]) -> int:
    data = load_seen()
    urls = {_norm_host(u) for u in data["urls"] if _norm_host(u)}
    emails = {clean_email(e) or "" for e in data["emails"]}
    emails.discard("")
    before = len(urls)

    for lead in leads:
        for host in store_keys(lead):
            urls.add(host)
        primary = clean_email(lead.get("primary_email") or "")
        if primary:
            emails.add(primary)
        for part in (lead.get("all_emails") or "").split(";"):
            cleaned = clean_email(part)
            if cleaned:
                emails.add(cleaned)

    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(
        json.dumps({"urls": sorted(urls), "emails": sorted(emails)}, indent=2),
        encoding="utf-8",
    )
    return len(urls) - before
