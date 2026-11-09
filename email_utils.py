"""Extract, validate, and clean email addresses."""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from email_validator import EmailNotValidError, validate_email

from config import DISPOSABLE_DOMAINS, EMAIL_BLOCKLIST_SUBSTRINGS

EMAIL_RE = re.compile(
    r"(?i)\b([a-z0-9][a-z0-9._%+\-]{0,63}@[a-z0-9][a-z0-9.\-]{1,253}\.[a-z]{2,})\b"
)

# Common false positives from JS / assets
ASSET_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")

# Personal / free inboxes — keep, but rank after brand @domain.com
FREE_MAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "msn.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "protonmail.com",
    "proton.me",
    "yandex.com",
    "mail.com",
}

# Preferred local-parts on the brand domain
ROLE_LOCALS = {
    "info",
    "contact",
    "hello",
    "hi",
    "support",
    "sales",
    "orders",
    "order",
    "help",
    "team",
    "admin",
    "enquiry",
    "inquiry",
    "care",
    "customerservice",
    "customer",
}


def extract_emails(text: str) -> set[str]:
    if not text:
        return set()
    found: set[str] = set()
    for match in EMAIL_RE.findall(text):
        cleaned = clean_email(match)
        if cleaned:
            found.add(cleaned)
    return found


def clean_email(raw: str) -> str | None:
    email = raw.strip().lower().rstrip(".,;:)>\"'")
    email = email.replace("%40", "@")

    if not email or "@" not in email:
        return None
    if any(ext in email for ext in ASSET_EXTS):
        return None
    if any(bad in email for bad in EMAIL_BLOCKLIST_SUBSTRINGS):
        return None

    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return None
    if domain in DISPOSABLE_DOMAINS:
        return None
    # Reject weird TLDs / truncated domains like "brand.com.we"
    tld = domain.rsplit(".", 1)[-1]
    if len(tld) < 2 or not tld.isalpha():
        return None
    if len(local) < 2 or local.startswith(".") or local.endswith("."):
        return None

    try:
        validated = validate_email(email, check_deliverability=False)
        return validated.normalized.lower()
    except EmailNotValidError:
        return None


def merge_emails(*groups: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for group in groups:
        for email in group:
            cleaned = clean_email(email)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                ordered.append(cleaned)
    return ordered


def hosts_from_store(store: dict | None = None, *urls: str) -> list[str]:
    """Collect brand hosts to prefer, e.g. salar.com from store URLs."""
    hosts: list[str] = []
    candidates: list[str] = list(urls)
    if store:
        for key in ("custom_domain", "url", "myshopify_url", "store_url"):
            val = store.get(key) or ""
            if val:
                candidates.append(val)

    for raw in candidates:
        host = (urlparse(raw).hostname or raw).lower().removeprefix("www.")
        if not host or host.endswith(".myshopify.com"):
            continue
        if host not in hosts:
            hosts.append(host)
    return hosts


def _email_rank(email: str, brand_hosts: list[str]) -> tuple:
    """
    Lower tuple = better (used as sort key).

    Priority:
      1. @salar.com matching the store's custom .com domain (+ role local)
      2. Other exact brand-domain matches (.pk / .com.pk / etc.)
      3. Any other .com brand-style address (not free mail)
      4. Free mail (gmail, yahoo, …)
      5. Everything else
    """
    local, _, domain = email.partition("@")
    domain = domain.lower()
    is_role = 0 if local in ROLE_LOCALS else 1
    is_free = domain in FREE_MAIL_DOMAINS

    # Exact match on store custom domain (salar.com)
    if brand_hosts and domain in brand_hosts:
        # Prefer .com brand domains first when multiple brand hosts exist
        com_boost = 0 if domain.endswith(".com") and not domain.endswith(".com.pk") else 1
        return (0, com_boost, is_role, email)

    # Brand-looking .com (not free mail) — still strong for outreach
    if domain.endswith(".com") and not is_free and not domain.endswith(".myshopify.com"):
        return (1, is_role, email)

    # Other custom TLDs (.pk, .com.pk, …)
    if not is_free and not domain.endswith(".myshopify.com"):
        return (2, is_role, email)

    if is_free:
        return (3, is_role, email)

    return (4, is_role, email)


def prioritize_emails(
    emails: Iterable[str],
    store: dict | None = None,
    *extra_urls: str,
) -> list[str]:
    """Dedupe + rank so primary_email prefers hello@salar.com over gmail."""
    merged = merge_emails(emails)
    brand_hosts = hosts_from_store(store, *extra_urls)
    return sorted(merged, key=lambda e: _email_rank(e, brand_hosts))