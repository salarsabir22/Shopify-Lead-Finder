"""Step 3 — dedupe, standardize, and export leads."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from config import CSV_FILENAME, OUTPUT_DIR
from email_utils import clean_email, merge_emails, prioritize_emails


def standardize_lead(store: dict, discovery: dict) -> dict:
    # Prefer brand @salar.com (custom .com) over gmail / other free mail
    emails = prioritize_emails(discovery.get("emails") or [], store)
    return {
        "store_url": store.get("url", "").rstrip("/"),
        "custom_domain": (store.get("custom_domain") or "").rstrip("/"),
        "myshopify_url": (store.get("myshopify_url") or "").rstrip("/"),
        "has_custom_domain": bool(store.get("has_custom_domain")),
        "shopify_verified": bool(store.get("shopify_verified")),
        "shopify_proof": store.get("shopify_proof") or "",
        "title": (store.get("title") or "").strip(),
        "primary_email": emails[0] if emails else "",
        "all_emails": "; ".join(emails),
        "email_count": len(emails),
        "location": store.get("location") or discovery.get("location") or "",
        "location_score": store.get("location_score", 0),
        "currency_hint": discovery.get("currency_hint") or "",
        "traffic_score": store.get("traffic_score", 0),
        "traffic_tier": store.get("traffic_tier") or "",
        "monthly_visits_est": store.get("monthly_visits_est", 0),
        "daily_visits_est": store.get("daily_visits_est", 0),
        "monthly_pageviews_est": store.get("monthly_pageviews_est", 0),
        "traffic_data_source": store.get("traffic_data_source") or "",
        "product_count": store.get("product_count", 0),
        "search_hits": store.get("search_hits", 0),
        "social_links": store.get("social_links", 0),
        "review_count_guess": store.get("review_count_guess", 0),
        "is_myshopify": store.get("is_myshopify", False),
        "source_query": store.get("source_query", ""),
        "snippet": (store.get("snippet") or "").replace("\n", " ").strip()[:300],
        "layer1": "; ".join(discovery.get("layers", {}).get("layer1_search") or []),
        "layer2": "; ".join(discovery.get("layers", {}).get("layer2_pages") or []),
        "layer3": "; ".join(discovery.get("layers", {}).get("layer3_web") or []),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def _lead_identity_keys(lead: dict) -> set[str]:
    from urllib.parse import urlparse

    keys: set[str] = set()
    for field in ("store_url", "custom_domain", "myshopify_url"):
        raw = (lead.get(field) or "").strip().lower()
        if not raw:
            continue
        if "://" not in raw:
            raw = "https://" + raw
        host = (urlparse(raw).hostname or "").lower().removeprefix("www.")
        if host:
            keys.add(host)
    return keys


def dedupe_leads(leads: list[dict]) -> list[dict]:
    """Dedupe by any store host (custom / myshopify) and by email."""
    unique: list[dict] = []
    seen_hosts: set[str] = set()
    seen_emails: set[str] = set()

    for lead in leads:
        hosts = _lead_identity_keys(lead)
        if hosts and hosts & seen_hosts:
            # Merge emails into the first matching lead
            for existing in unique:
                if _lead_identity_keys(existing) & hosts:
                    merged = merge_emails(
                        (existing.get("all_emails") or "").split(";"),
                        (lead.get("all_emails") or "").split(";"),
                    )
                    existing["all_emails"] = "; ".join(merged)
                    existing["primary_email"] = merged[0] if merged else existing.get(
                        "primary_email", ""
                    )
                    existing["email_count"] = len(merged)
                    break
            continue

        primary = clean_email(lead.get("primary_email") or "")
        all_cleaned = [
            e
            for e in (
                clean_email(p) for p in (lead.get("all_emails") or "").split(";")
            )
            if e
        ]
        if primary and primary in seen_emails:
            continue
        if any(e in seen_emails for e in all_cleaned):
            continue

        seen_hosts |= hosts
        if primary:
            seen_emails.add(primary)
        seen_emails.update(all_cleaned)
        unique.append(lead)

    return unique


def save_leads(leads: list[dict], niche: str, location: str = "") -> tuple[Path, Path]:
    out = Path(OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)

    safe_niche = "".join(c if c.isalnum() or c in "-_" else "_" for c in niche.lower())[:40]
    safe_loc = "".join(c if c.isalnum() or c in "-_" else "_" for c in (location or "global").lower())[:20]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{safe_loc}_{safe_niche}" if safe_loc != "global" else safe_niche
    csv_path = out / f"{prefix}_{CSV_FILENAME}"
    json_path = out / f"{prefix}_{stamp}.json"

    fieldnames = [
        "store_url",
        "custom_domain",
        "myshopify_url",
        "has_custom_domain",
        "shopify_verified",
        "shopify_proof",
        "title",
        "primary_email",
        "all_emails",
        "email_count",
        "location",
        "location_score",
        "currency_hint",
        "traffic_score",
        "traffic_tier",
        "monthly_visits_est",
        "daily_visits_est",
        "monthly_pageviews_est",
        "traffic_data_source",
        "product_count",
        "search_hits",
        "social_links",
        "review_count_guess",
        "is_myshopify",
        "source_query",
        "snippet",
        "layer1",
        "layer2",
        "layer3",
        "scraped_at",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow({k: lead.get(k, "") for k in fieldnames})

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)

    return csv_path, json_path


def summary_stats(leads: list[dict]) -> dict:
    with_email = sum(1 for L in leads if L.get("primary_email"))
    total = len(leads)
    rate = (with_email / total * 100) if total else 0.0
    return {
        "total_stores": total,
        "with_email": with_email,
        "without_email": total - with_email,
        "discovery_rate_pct": round(rate, 1),
    }