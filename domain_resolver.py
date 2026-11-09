"""
Resolve *.myshopify.com → custom domain, and verify Shopify on custom domains.

Most real stores use brand.com / brand.pk — the myshopify URL is only the
admin/backend hostname. Emails almost always live on the custom domain.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import requests

from config import HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT

session = requests.Session()
session.headers.update(HEADERS)

# Proofs we look for in HTML / headers / URL
SHOPIFY_FINGERPRINTS = (
    ("cdn.shopify.com", "cdn.shopify.com"),
    ("cdn.shopifycdn.net", "cdn.shopifycdn.net"),
    ("myshopify.com", "myshopify.com"),
    ("Shopify.theme", "Shopify.theme"),
    ("shopify-section", "shopify-section"),
    ("shopify-payment-button", "shopify-payment-button"),
    ("window.Shopify", "window.Shopify"),
    ("shopify.theme", "shopify.theme"),
    ("/cdn/shop/", "/cdn/shop/"),
    ("Shopify.shop", "Shopify.shop"),
    ("x-shopify", "x-shopify header/meta"),
)

CANONICAL_RE = re.compile(
    r"""(?is)<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']"""
    r"|"
    r"""<meta[^>]+property=["']og:url["'][^>]+content=["']([^"']+)["']"""
)
SHOP_HANDLE_RE = re.compile(
    r"""(?i)(?:Shopify\.shop\s*=\s*[\"']|"shop":\s*")([a-z0-9][a-z0-9\-]*\.myshopify\.com)[\"']"""
)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_myshopify_host(url: str) -> bool:
    return _host(url).endswith(".myshopify.com")


def _base(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return url.rstrip("/")
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}"


def collect_shopify_proofs(html: str, headers: dict | None = None, url: str = "") -> list[str]:
    """Return human-readable evidence that this page is a Shopify store."""
    proofs: list[str] = []
    if is_myshopify_host(url):
        proofs.append(f"url:{_host(url)}")

    blob = html or ""
    for needle, label in SHOPIFY_FINGERPRINTS:
        if needle.lower() in blob.lower():
            if label not in proofs:
                proofs.append(label)

    if headers:
        for key, val in headers.items():
            lk = key.lower()
            if "shopify" in lk or (isinstance(val, str) and "shopify" in val.lower()):
                proof = f"header:{key}"
                if proof not in proofs:
                    proofs.append(proof)

    handle = SHOP_HANDLE_RE.search(blob)
    if handle:
        proof = f"shop:{handle.group(1).lower()}"
        if proof not in proofs:
            proofs.append(proof)

    return proofs


def looks_like_shopify(html: str, headers: dict | None = None, url: str = "") -> bool:
    return bool(collect_shopify_proofs(html, headers, url))


def resolve_custom_domain(store_url: str) -> dict:
    """
    Visit the store URL, verify Shopify, and find the public custom domain.

    Returns keys:
      url, myshopify_url, custom_domain, is_shopify, shopify_proof,
      resolved_via
    """
    original = store_url.rstrip("/")
    result = {
        "url": original,
        "myshopify_url": original if is_myshopify_host(original) else "",
        "custom_domain": "" if is_myshopify_host(original) else original,
        "is_shopify": False,
        "shopify_proof": "",
        "resolved_via": "same",
    }

    try:
        resp = session.get(original + "/", timeout=REQUEST_TIMEOUT, allow_redirects=True)
        time.sleep(REQUEST_DELAY)
    except requests.RequestException:
        result["resolved_via"] = "failed"
        # Bare *.myshopify.com still counts even if fetch failed
        if is_myshopify_host(original):
            result["is_shopify"] = True
            result["shopify_proof"] = f"url:{_host(original)}"
        return result

    final = _base(str(resp.url))
    html = resp.text if resp.ok else ""
    headers = {k: str(v) for k, v in resp.headers.items()}

    proofs = collect_shopify_proofs(html, headers, original)
    proofs += [p for p in collect_shopify_proofs(html, headers, final) if p not in proofs]
    result["is_shopify"] = bool(proofs)
    result["shopify_proof"] = "; ".join(proofs[:6])

    # Pull myshopify handle from page JS if present
    handle = SHOP_HANDLE_RE.search(html or "")
    if handle and not result["myshopify_url"]:
        result["myshopify_url"] = f"https://{handle.group(1).lower()}"

    # 1) Redirect: store.myshopify.com → www.brand.com
    if final and _host(final) != _host(original) and not is_myshopify_host(final):
        result["custom_domain"] = final
        result["url"] = final
        result["resolved_via"] = "redirect"
        if is_myshopify_host(original):
            result["myshopify_url"] = original
            if not result["is_shopify"]:
                result["is_shopify"] = True
                result["shopify_proof"] = f"url:{_host(original)}"
        return result

    # 2) Canonical / og:url
    if html:
        match = CANONICAL_RE.search(html)
        if match:
            canon = (match.group(1) or match.group(2) or "").strip()
            if canon:
                canon_base = _base(canon)
                if not is_myshopify_host(canon_base) and _host(canon_base):
                    result["custom_domain"] = canon_base
                    result["url"] = canon_base
                    result["resolved_via"] = "canonical"
                    if is_myshopify_host(original):
                        result["myshopify_url"] = original
                    return result

    # 3) Custom domain confirmed via fingerprint
    if not is_myshopify_host(original) and result["is_shopify"]:
        result["custom_domain"] = original
        result["url"] = original
        result["resolved_via"] = "fingerprint"
        return result

    result["url"] = original
    result["resolved_via"] = "same"
    return result


def enrich_stores_with_domains(stores: list[dict]) -> list[dict]:
    """
    Resolve custom domains and KEEP ONLY verified Shopify stores.
    """
    enriched: list[dict] = []
    seen_final: set[str] = set()

    for store in stores:
        resolved = resolve_custom_domain(store["url"])

        # Hard rule: no Shopify proof → no lead (no emails either)
        if not resolved.get("is_shopify"):
            continue

        final_url = resolved["url"].rstrip("/").lower()
        if final_url in seen_final:
            continue
        seen_final.add(final_url)

        store = dict(store)
        store["url"] = resolved["url"]
        store["myshopify_url"] = resolved.get("myshopify_url") or ""
        store["custom_domain"] = resolved.get("custom_domain") or ""
        store["domain_resolved_via"] = resolved.get("resolved_via") or ""
        store["shopify_verified"] = True
        store["shopify_proof"] = resolved.get("shopify_proof") or ""
        store["is_myshopify"] = is_myshopify_host(store["url"])
        store["has_custom_domain"] = bool(store["custom_domain"]) and not is_myshopify_host(
            store["custom_domain"]
        )
        enriched.append(store)

    return enriched
