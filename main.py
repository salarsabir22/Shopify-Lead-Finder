#!/usr/bin/env python3
"""Local CLI — saves CSV/JSON under output/."""

from __future__ import annotations

import argparse
import sys

from config import MAX_STORES
from locations import LOCATIONS
from pipeline import run_scrape


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Shopify lead finder (local CSV export).")
    p.add_argument("niche", help='e.g. "clothing"')
    p.add_argument("-n", "--max-stores", type=int, default=MAX_STORES)
    p.add_argument(
        "-c",
        "--country",
        default="pakistan",
        choices=sorted(LOCATIONS.keys()),
    )
    p.add_argument("--with-email-only", action="store_true")
    p.add_argument("--loose", action="store_true")
    p.add_argument("--min-traffic", type=int, default=0)
    p.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Do not skip stores already in output/seen_leads.json",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    niche = args.niche.strip()
    if not niche:
        print("Niche cannot be empty.")
        return 1

    print(f"\n=== Shopify Lead Scraper (local) ===")
    print(f"Niche:   {niche}")
    print(f"Country: {args.country}")
    print(f"Max:     {args.max_stores}\n")

    def on_progress(stage: str, progress: float, extra=None) -> None:
        print(f"[{int(progress * 100):3d}%] {stage}")

    try:
        result = run_scrape(
            niche,
            max_stores=args.max_stores,
            country=args.country,
            with_email_only=args.with_email_only,
            loose=args.loose,
            min_traffic_score=args.min_traffic,
            skip_seen=not args.allow_duplicates,
            on_progress=on_progress,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    stats = result["stats"]
    print("\n--- Results ---")
    print(f"Stores:        {stats['total_stores']}")
    print(f"With email:    {stats['with_email']}")
    print(f"Skipped dupes: {result.get('skipped_duplicates', 0)}")
    print(f"\nCSV:  {result['csv_path']}")
    print(f"JSON: {result['json_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
