"""Shared scrape pipeline — local files by default (CSV + seen_leads.json)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleaner import dedupe_leads, save_leads, standardize_lead, summary_stats
from domain_resolver import enrich_stores_with_domains
from email_finder import discover_emails
from seen_leads import filter_new_stores, remember_leads, seen_sets
from store_finder import find_stores
from traffic_rank import enrich_lead_with_traffic

ProgressCb = Callable[[str, float, dict | None], None]


def _noop(stage: str, progress: float, extra: dict | None = None) -> None:
    return None


def run_scrape(
    niche: str,
    *,
    max_stores: int = 10,
    country: str = "pakistan",
    with_email_only: bool = False,
    loose: bool = False,
    min_traffic_score: int = 0,
    skip_seen: bool = True,
    on_progress: ProgressCb | None = None,
) -> dict:
    notify = on_progress or _noop
    niche = niche.strip()
    if not niche:
        raise ValueError("Niche cannot be empty.")

    seen_urls, seen_emails = seen_sets() if skip_seen else (set(), set())
    if skip_seen and (seen_urls or seen_emails):
        notify(
            f"Skipping {len(seen_urls)} known stores / {len(seen_emails)} emails…",
            0.03,
            {"phase": "dedupe"},
        )

    notify("Finding stores…", 0.05, {"phase": "search"})
    fetch_n = max(max_stores * 4, max_stores + len(seen_urls))
    stores = find_stores(
        niche,
        max_stores=fetch_n,
        location=country,
        require_location_match=not loose,
    )

    notify(
        f"Resolving custom domains ({len(stores)} candidates)…",
        0.12,
        {"phase": "resolve", "candidates": len(stores)},
    )
    stores = enrich_stores_with_domains(stores)

    skipped = 0
    if skip_seen:
        before = len(stores)
        stores = filter_new_stores(stores, seen_urls)
        skipped = before - len(stores)

    stores = stores[:max_stores]
    custom_count = sum(1 for s in stores if s.get("has_custom_domain"))

    if not stores:
        notify("No new stores found", 1.0, {"phase": "done"})
        return {
            "leads": [],
            "stats": summary_stats([]),
            "csv_path": None,
            "json_path": None,
            "custom_domain_count": 0,
            "skipped_duplicates": skipped,
        }

    leads: list[dict] = []
    total = len(stores)
    for i, store in enumerate(stores):
        pct = 0.15 + (0.75 * (i / max(total, 1)))
        notify(
            f"Emails + traffic {i + 1}/{total}: {store.get('url', '')}",
            pct,
            {
                "phase": "emails",
                "current": i + 1,
                "total": total,
                "url": store.get("url"),
            },
        )
        discovery = discover_emails(store, location=country)
        store["location_score"] = discovery.get(
            "location_score", store.get("location_score", 0)
        )
        store["location"] = discovery.get("location", store.get("location", ""))
        lead = standardize_lead(store, discovery)
        lead = enrich_lead_with_traffic(store, lead)

        if skip_seen:
            primary = (lead.get("primary_email") or "").lower()
            if primary and primary in seen_emails:
                skipped += 1
                continue
        leads.append(lead)

    notify("Cleaning + exporting…", 0.95, {"phase": "export"})
    leads = dedupe_leads(leads)

    if min_traffic_score > 0:
        leads = [
            L for L in leads if int(L.get("traffic_score") or 0) >= min_traffic_score
        ]

    leads.sort(
        key=lambda L: (
            -int(L.get("monthly_visits_est") or 0),
            -int(L.get("traffic_score") or 0),
            -int(L.get("location_score") or 0),
            L.get("store_url") or "",
        )
    )
    if with_email_only:
        leads = [L for L in leads if L.get("primary_email")]

    csv_path = json_path = None
    if leads:
        csv_path, json_path = save_leads(leads, niche, location=country)
        if skip_seen:
            remember_leads(leads)

    stats = summary_stats(leads)
    notify("Done", 1.0, {"phase": "done", "stats": stats})
    return {
        "leads": leads,
        "stats": stats,
        "csv_path": Path(csv_path) if csv_path else None,
        "json_path": Path(json_path) if json_path else None,
        "custom_domain_count": custom_count,
        "skipped_duplicates": skipped,
    }
