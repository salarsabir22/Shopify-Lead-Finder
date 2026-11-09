"""Step 1 — find Shopify stores via free DuckDuckGo search."""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from ddgs import DDGS

from config import MAX_STORES, RESULTS_PER_QUERY
from email_utils import extract_emails
from locations import location_score, looks_like_location, resolve_location

MYSHOPIFY_RE = re.compile(
    r"(?i)https?://([a-z0-9][a-z0-9\-]*\.myshopify\.com)(?:/[^\s\"'<>]*)?"
)


def build_queries(niche: str, location: str | None = None) -> list[str]:
    niche = niche.strip()
    loc = resolve_location(location)
    queries: list[str] = []

    if loc["key"] == "global":
        return [
            f"{niche} site:myshopify.com",
            f'"{niche}" site:myshopify.com',
            f"{niche} online store site:myshopify.com",
            f'{niche} "powered by Shopify"',
            f"{niche} Shopify store -site:shopify.com",
        ]

    # Pakistan / geo-focused — .myshopify.com, .pk, AND .com custom domains
    geo = loc["query_terms"]
    primary = geo[0]  # e.g. Pakistan
    cities = geo[2:5]  # Karachi, Lahore, Islamabad

    queries.extend(
        [
            # myshopify subdomain hits
            f"{niche} {primary} site:myshopify.com",
            f'"{niche}" {primary} site:myshopify.com',
            f"{niche} {primary} online store site:myshopify.com",
            f"{niche} shop {primary} site:myshopify.com",
            # custom domains: brand.pk
            f"{niche} online store site:.pk",
            f"{niche} shop site:.pk",
            f"{niche} buy online Pakistan site:.pk",
            f"{niche} store Pakistan .pk",
            # custom domains: brand.com (very common in Pakistan)
            f"{niche} {primary} Shopify",
            f'{niche} {primary} "powered by Shopify"',
            f"{niche} {primary} Shopify store",
            f'{niche} Pakistan "powered by Shopify" -site:myshopify.com',
            f"{niche} buy online Pakistan Shopify",
            f"{niche} online shopping Pakistan Shopify",
            f"{niche} Pakistan store PKR Shopify",
            f'"{niche}" Pakistan online store',
        ]
    )
    for city in cities:
        queries.append(f"{niche} {city} site:myshopify.com")
        queries.append(f"{niche} {city} Shopify store")
        queries.append(f"{niche} {city} site:.pk")
        queries.append(f'{niche} {city} "powered by Shopify"')
        queries.append(f"{niche} {city} online store")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


def normalize_store_url(url: str) -> str | None:
    if not url:
        return None
    url = url.strip()
    match = MYSHOPIFY_RE.search(url)
    if match:
        return f"https://{match.group(1).lower()}"

    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    if not host or host.startswith("www.google.") or "duckduckgo" in host:
        return None
    if host.endswith(".myshopify.com") or "." in host:
        scheme = parsed.scheme or "https"
        return f"{scheme}://{host}"
    return None


def is_myshopify(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.endswith(".myshopify.com")


def find_stores(
    niche: str,
    max_stores: int = MAX_STORES,
    results_per_query: int = RESULTS_PER_QUERY,
    location: str | None = "pakistan",
    require_location_match: bool = True,
) -> list[dict]:
    """
    Search DuckDuckGo for Shopify stores in a niche (+ optional country).

    Returns list of dicts with url, title, snippet, emails_from_search, etc.
    """
    stores: dict[str, dict] = {}
    loc = resolve_location(location)
    queries = build_queries(niche, location)

    with DDGS() as ddgs:
        for query in queries:
            if len(stores) >= max_stores:
                break
            try:
                results = list(ddgs.text(query, max_results=results_per_query))
            except Exception as exc:
                print(f"  [warn] search failed for '{query}': {exc}")
                time.sleep(2)
                continue

            for item in results:
                href = item.get("href") or item.get("link") or ""
                title = item.get("title") or ""
                body = item.get("body") or item.get("snippet") or ""
                blob = f"{title} {body} {href}"

                candidates: list[str] = []
                store_url = normalize_store_url(href)
                if store_url:
                    candidates.append(store_url)
                for match in MYSHOPIFY_RE.finditer(blob):
                    candidates.append(f"https://{match.group(1).lower()}")

                for candidate in candidates:
                    if candidate in stores:
                        continue

                    host = (urlparse(candidate).hostname or "").lower()
                    preferred = loc.get("preferred_tlds") or ()
                    is_preferred_tld = any(host.endswith(t) for t in preferred) or is_myshopify(
                        candidate
                    )

                    # Geo query already targets Pakistan — allow .com / .pk / myshopify
                    # through; domain_resolver later drops non-Shopify sites.
                    from_geo_query = loc["key"] != "global"
                    location_ok = looks_like_location(blob, candidate, loc, min_score=1)

                    if require_location_match and not location_ok:
                        if not (from_geo_query and is_preferred_tld):
                            continue

                    score = location_score(blob, candidate, loc)
                    # Small boost for .com when snippet/query is Pakistan-related
                    if host.endswith(".com") and not host.endswith(".myshopify.com"):
                        if location_ok or "pakistan" in query.lower():
                            score += 2

                    stores[candidate] = {
                        "url": candidate,
                        "title": title,
                        "snippet": body,
                        "emails_from_search": sorted(extract_emails(blob)),
                        "source_query": query,
                        "is_myshopify": is_myshopify(candidate),
                        "location": loc["label"],
                        "location_score": score,
                    }
                    if len(stores) >= max_stores:
                        break

            time.sleep(1.0)

    ordered = sorted(
        stores.values(),
        key=lambda s: (-s.get("location_score", 0), not s["is_myshopify"], s["url"]),
    )
    return ordered[:max_stores]
