"""
Estimate store popularity WITHOUT paid tools (SimilarWeb / StoreLeads).

Important: this is a PROXY score — not real revenue or Exact traffic.
True top-seller / traffic data is usually paid. We combine free public signals:

  1. Shopify /products.json — catalog size + review hints
  2. Homepage signals — social links, review apps, bestsellers
  3. Search visibility — DuckDuckGo hit count for the brand domain
  4. Custom .com domain — usually more established than bare myshopify

Use traffic_score to sort leads; treat higher = likely more established / visible.
"""

from __future__ import annotations

import math
import re
import time
from urllib.parse import urlparse

import requests
from ddgs import DDGS

from config import HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT

session = requests.Session()
session.headers.update(HEADERS)

REVIEW_APP_HINTS = (
    "judge.me",
    "loox.io",
    "stamped.io",
    "yotpo",
    "okendo",
    "reviews.io",
    "rivyo",
    "productreviews.shopifycdn.com",
)

SOCIAL_HINTS = (
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
)

BESTSELLER_HINTS = (
    "bestseller",
    "best-seller",
    "best seller",
    "top seller",
    "most popular",
    "trending",
)


def _base(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}"


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _fetch_json(url: str) -> dict | list | None:
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        time.sleep(REQUEST_DELAY * 0.5)
        if not resp.ok:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _fetch_text(url: str) -> str:
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        time.sleep(REQUEST_DELAY * 0.5)
        if not resp.ok:
            return ""
        return resp.text or ""
    except requests.RequestException:
        return ""


def product_signals(store_url: str) -> dict:
    """Use public Shopify products.json (no API key)."""
    base = _base(store_url)
    data = _fetch_json(f"{base}/products.json?limit=250")
    products = []
    if isinstance(data, dict):
        products = data.get("products") or []

    review_mentions = 0
    variants = 0
    for p in products:
        variants += len(p.get("variants") or [])
        blob = " ".join(
            [
                str(p.get("title") or ""),
                str(p.get("body_html") or ""),
                str(p.get("tags") or ""),
            ]
        ).lower()
        if "review" in blob or "rating" in blob:
            review_mentions += 1

    return {
        "product_count": len(products),
        "variant_count": variants,
        "product_review_mentions": review_mentions,
    }


def homepage_signals(store_url: str) -> dict:
    html = _fetch_text(_base(store_url) + "/")
    lower = html.lower()
    social = sum(1 for s in SOCIAL_HINTS if s in lower)
    review_apps = sum(1 for r in REVIEW_APP_HINTS if r in lower)
    bestsellers = sum(1 for b in BESTSELLER_HINTS if b in lower)

    # Rough review-count scrape from common widgets (best-effort)
    review_count = 0
    for pattern in (
        r'(\d[\d,]*)\s+reviews?',
        r'"reviewCount"\s*:\s*"?(\d+)"?',
        r'data-rating-count=["\'](\d+)',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            try:
                review_count = max(review_count, int(m.group(1).replace(",", "")))
            except ValueError:
                pass

    return {
        "social_links": social,
        "review_apps": review_apps,
        "bestseller_mentions": bestsellers,
        "review_count_guess": review_count,
        "html_bytes": len(html),
    }


def search_visibility(store_url: str) -> dict:
    """How visible is this brand on DuckDuckGo? Free proxy for demand."""
    host = _host(store_url)
    if not host:
        return {"search_hits": 0}

    brand = host.split(".")[0]
    query = f'"{host}" OR "{brand}" shop OR store'
    hits = 0
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=25))
            hits = len(results)
    except Exception:
        hits = 0
    time.sleep(1.0)
    return {"search_hits": hits}


def _parse_int(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return int(re.sub(r"[^\d]", "", raw))
    except ValueError:
        return 0


def fetch_monthly_visits(store_url: str) -> dict:
    """
    Free visit estimates from StatShow public pages.

    These are third-party ESTIMATES (not Google Analytics).
    Small / new stores often return 0.
    """
    host = _host(store_url)
    empty = {
        "monthly_visits_est": 0,
        "daily_visits_est": 0,
        "monthly_pageviews_est": 0,
        "traffic_data_source": "",
    }
    if not host or host.endswith(".myshopify.com"):
        # StatShow rarely has bare myshopify hosts — try custom domain only
        return empty

    url = f"https://www.statshow.com/www/{host}"
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        time.sleep(REQUEST_DELAY)
    except requests.RequestException:
        return empty

    if not resp.ok or not resp.text:
        return empty

    html = resp.text
    m_vis = re.search(r"Monthly Visitors:\s*<span[^>]*>([\d,]+)</span>", html, re.I)
    d_vis = re.search(r"Daily Visitors:\s*<span[^>]*>([\d,]+)</span>", html, re.I)
    m_pv = re.search(r"Monthly Pageviews:\s*<span[^>]*>([\d,]+)</span>", html, re.I)

    monthly_visits = _parse_int(m_vis.group(1) if m_vis else None)
    daily_visits = _parse_int(d_vis.group(1) if d_vis else None)
    monthly_pv = _parse_int(m_pv.group(1) if m_pv else None)

    if not monthly_visits and not daily_visits:
        return empty

    return {
        "monthly_visits_est": monthly_visits,
        "daily_visits_est": daily_visits,
        "monthly_pageviews_est": monthly_pv,
        "traffic_data_source": "statshow_estimate",
    }


def compute_traffic_score(store: dict) -> dict:
    """
    Combine free signals into traffic_score (0–100) + estimated visits.
    """
    url = store.get("custom_domain") or store.get("url") or ""
    products = product_signals(url)
    home = homepage_signals(url)
    search = search_visibility(url)
    visits = fetch_monthly_visits(url)

    # Catalog size (cap influence)
    pc = products["product_count"]
    catalog_pts = min(25, int(10 * math.log10(pc + 1) * 2.5))

    # Reviews / social proof
    review_pts = min(15, home["review_apps"] * 5 + min(home["review_count_guess"] // 50, 8))
    social_pts = min(10, home["social_links"] * 2)
    bestseller_pts = min(8, home["bestseller_mentions"] * 2)

    # Search visibility
    search_pts = min(12, search["search_hits"])

    # Domain maturity proxy
    domain_pts = 0
    host = _host(url)
    if host.endswith(".com") and not host.endswith(".myshopify.com"):
        domain_pts += 4
    if host.endswith(".pk") or host.endswith(".com.pk"):
        domain_pts += 3
    if store.get("has_custom_domain"):
        domain_pts += 2
    domain_pts = min(8, domain_pts)

    # Real visit estimate (strongest free signal when available)
    mv = visits["monthly_visits_est"]
    if mv >= 1_000_000:
        visit_pts = 30
    elif mv >= 100_000:
        visit_pts = 25
    elif mv >= 20_000:
        visit_pts = 20
    elif mv >= 5_000:
        visit_pts = 15
    elif mv >= 1_000:
        visit_pts = 10
    elif mv > 0:
        visit_pts = 5
    else:
        visit_pts = 0

    score = (
        catalog_pts
        + review_pts
        + social_pts
        + bestseller_pts
        + search_pts
        + domain_pts
        + visit_pts
    )
    score = int(max(0, min(100, score)))

    if mv >= 20_000 or score >= 70:
        tier = "high"
    elif mv >= 1_000 or score >= 40:
        tier = "medium"
    else:
        tier = "low"

    note = (
        "monthly_visits_est from free StatShow estimates (not GA). "
        "Small stores may show 0."
        if visits["traffic_data_source"]
        else "No public visit estimate found — traffic_score uses catalog/social/search proxies only."
    )

    return {
        "traffic_score": score,
        "traffic_tier": tier,
        "monthly_visits_est": visits["monthly_visits_est"],
        "daily_visits_est": visits["daily_visits_est"],
        "monthly_pageviews_est": visits["monthly_pageviews_est"],
        "traffic_data_source": visits["traffic_data_source"],
        "product_count": products["product_count"],
        "variant_count": products["variant_count"],
        "search_hits": search["search_hits"],
        "social_links": home["social_links"],
        "review_apps": home["review_apps"],
        "review_count_guess": home["review_count_guess"],
        "bestseller_mentions": home["bestseller_mentions"],
        "traffic_note": note,
    }


def enrich_lead_with_traffic(store: dict, lead: dict) -> dict:
    metrics = compute_traffic_score(store)
    lead = dict(lead)
    lead.update(metrics)
    return lead
