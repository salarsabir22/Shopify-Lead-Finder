"""Step 2 — three-layer email discovery."""

from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

from config import CONTACT_PATHS, HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT
from email_utils import extract_emails, merge_emails, prioritize_emails
from locations import location_score, resolve_location


def detect_currency_hint(html: str, location: str | None = "pakistan") -> str:
    """Pick up PKR / Rs signals that confirm a Pakistan store."""
    if not html:
        return ""
    loc = resolve_location(location)
    upper = html.upper()
    for hint in loc.get("currency_hints") or ():
        if hint.upper() in upper:
            return hint.strip()
    return ""

session = requests.Session()
session.headers.update(HEADERS)


def _fetch(url: str) -> str:
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400:
            return ""
        # Skip non-HTML
        ctype = resp.headers.get("Content-Type", "")
        if "text" not in ctype and "html" not in ctype and ctype:
            return ""
        return resp.text
    except requests.RequestException:
        return ""


def _emails_from_html(html: str) -> set[str]:
    if not html:
        return set()
    emails = extract_emails(html)
    soup = BeautifulSoup(html, "lxml")

    # mailto: links
    for a in soup.select('a[href^="mailto:"]'):
        href = a.get("href", "")
        addr = href.split(":", 1)[-1].split("?", 1)[0]
        emails |= extract_emails(addr)

    # Visible text pass (catches obfuscated less often, but helps)
    emails |= extract_emails(soup.get_text(" ", strip=True))
    return emails


def layer1_from_search(store: dict) -> list[str]:
    """Fast wins — emails already present in search snippets."""
    return list(store.get("emails_from_search") or [])


def layer2_domain_pages(store_url: str) -> list[str]:
    """Scrape homepage + common contact / policy pages on the store domain."""
    found: set[str] = set()
    base = store_url.rstrip("/")

    for path in CONTACT_PATHS:
        url = urljoin(base + "/", path.lstrip("/")) if path != "/" else base + "/"
        html = _fetch(url)
        found |= _emails_from_html(html)
        time.sleep(REQUEST_DELAY)

        # Early exit if we already have a few solid emails
        if len(found) >= 3:
            break

    return sorted(found)


def layer3_web_search(store_url: str, extra_hosts: list[str] | None = None) -> list[str]:
    """
    Last layer — search the open web for contact emails tied to this store.
    Free alternative to paid extractors (Hunter, etc.).
    Works for custom domains (brand.pk) and myshopify hosts.
    """
    host = (urlparse(store_url).hostname or "").lower()
    if not host:
        return []

    # Strip www. for cleaner queries
    bare = host.removeprefix("www.")
    hosts = [bare]
    for h in extra_hosts or []:
        h = (urlparse(h).hostname or h).lower().removeprefix("www.")
        if h and h not in hosts:
            hosts.append(h)

    queries = []
    for h in hosts:
        queries.extend(
            [
                f'"{h}" email OR contact OR "@{h}"',
                f'site:{h} contact',
                f'"{h}" "@gmail.com" OR "@yahoo.com" OR "@hotmail.com"',
            ]
        )

    found: set[str] = set()
    with DDGS() as ddgs:
        for query in queries:
            try:
                results = list(ddgs.text(query, max_results=10))
            except Exception:
                time.sleep(2)
                continue

            for item in results:
                blob = " ".join(
                    [
                        item.get("title") or "",
                        item.get("body") or "",
                        item.get("href") or "",
                    ]
                )
                found |= extract_emails(blob)

            time.sleep(1.0)
            if len(found) >= 5:
                break

    # Layer 3 is noisy — ONLY keep emails on the store's own domain(s).
    # Never return random third-party inboxes (Shein, other brands, etc.).
    def _is_own(email: str) -> bool:
        return any(email.endswith("@" + h) for h in hosts)

    own = [e for e in found if _is_own(e)]
    return merge_emails(own)


def discover_emails(store: dict, location: str | None = "pakistan") -> dict:
    """
    Run all three layers for one store.
    Returns emails + which layer produced them.
    """
    url = store["url"]
    by_layer: dict[str, list[str]] = {
        "layer1_search": [],
        "layer2_pages": [],
        "layer3_web": [],
    }

    by_layer["layer1_search"] = layer1_from_search(store)

    homepage_html = _fetch(url.rstrip("/") + "/")
    time.sleep(REQUEST_DELAY)

    if len(by_layer["layer1_search"]) < 1:
        by_layer["layer2_pages"] = layer2_domain_pages(url)
    else:
        by_layer["layer2_pages"] = sorted(_emails_from_html(homepage_html))

    combined_so_far = merge_emails(
        by_layer["layer1_search"], by_layer["layer2_pages"]
    )
    if len(combined_so_far) < 1:
        extras = []
        if store.get("myshopify_url"):
            extras.append(store["myshopify_url"])
        if store.get("custom_domain"):
            extras.append(store["custom_domain"])
        by_layer["layer3_web"] = layer3_web_search(url, extra_hosts=extras)

    all_emails = prioritize_emails(
        merge_emails(
            by_layer["layer1_search"],
            by_layer["layer2_pages"],
            by_layer["layer3_web"],
        ),
        store,
        url,
    )

    loc = resolve_location(location)
    currency = detect_currency_hint(homepage_html, location)
    page_score = location_score(homepage_html[:8000], url, loc)
    total_score = int(store.get("location_score") or 0) + page_score
    if currency:
        total_score += 3

    return {
        "emails": all_emails,
        "primary_email": all_emails[0] if all_emails else "",
        "email_count": len(all_emails),
        "layers": by_layer,
        "location": loc["label"],
        "location_score": total_score,
        "currency_hint": currency,
    }