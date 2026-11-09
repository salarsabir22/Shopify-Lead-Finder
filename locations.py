"""Country / region targeting for store discovery."""

from __future__ import annotations

from urllib.parse import urlparse

# Preset regions. Key = CLI value (lowercase).
LOCATIONS: dict[str, dict] = {
    "pakistan": {
        "label": "Pakistan",
        "query_terms": [
            "Pakistan",
            "Pakistani",
            "Karachi",
            "Lahore",
            "Islamabad",
            "Rawalpindi",
            "Faisalabad",
            "PK",
        ],
        "signals": (
            "pakistan",
            "pakistani",
            "karachi",
            "lahore",
            "islamabad",
            "rawalpindi",
            "faisalabad",
            "multan",
            "peshawar",
            "gujranwala",
            "hyderabad",
            "sialkot",
            "quetta",
            " pkr",
            "rs.",
            "rs ",
            "rupees",
            "cod pakistan",
            "cash on delivery",
            "shipping to pakistan",
            "deliver to pakistan",
            ".pk",
            ".com.pk",
        ),
        # Strong TLD boost — .com alone is NOT enough (too many global stores)
        "tld_hints": (".pk", ".com.pk"),
        # Accepted public domains after Shopify fingerprint check
        "preferred_tlds": (".pk", ".com.pk", ".com"),
        "currency_hints": ("PKR", "Rs.", "Rs "),
    },
    "global": {
        "label": "Global",
        "query_terms": [],
        "signals": (),
        "tld_hints": (),
        "currency_hints": (),
    },
}


def resolve_location(name: str | None) -> dict:
    key = (name or "global").strip().lower()
    if key not in LOCATIONS:
        known = ", ".join(sorted(LOCATIONS))
        raise ValueError(f"Unknown location '{name}'. Choose one of: {known}")
    return {"key": key, **LOCATIONS[key]}


def location_score(text: str, url: str, loc: dict) -> int:
    """Higher = more likely this store is in/for the target country."""
    if loc["key"] == "global":
        return 0

    blob = f"{text} {url}".lower()
    score = 0

    host = (urlparse(url).hostname or "").lower()
    for tld in loc.get("tld_hints") or ():
        if host.endswith(tld):
            score += 5

    for signal in loc.get("signals") or ():
        if signal.lower() in blob:
            score += 1

    return score


def looks_like_location(text: str, url: str, loc: dict, min_score: int = 1) -> bool:
    if loc["key"] == "global":
        return True
    return location_score(text, url, loc) >= min_score