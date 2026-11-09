"""Shared settings for the local Shopify lead scraper."""

# How many search result pages / stores to collect
MAX_STORES = 50
RESULTS_PER_QUERY = 30

# Be polite — delays between HTTP requests (seconds)
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Common Shopify pages that often list contact emails
CONTACT_PATHS = [
    "/",
    "/pages/contact",
    "/pages/contact-us",
    "/pages/about",
    "/pages/about-us",
    "/pages/about-us-1",
    "/pages/faq",
    "/pages/shipping-policy",
    "/pages/privacy-policy",
    "/pages/refund-policy",
    "/pages/terms-of-service",
    "/policies/contact-information",
    "/policies/privacy-policy",
    "/policies/refund-policy",
    "/policies/terms-of-service",
]

# Domains that are almost never the store owner
DISPOSABLE_DOMAINS = {
    "example.com",
    "email.com",
    "domain.com",
    "newsletter.com",
    "sentry.io",
    "wixpress.com",
    "shopify.com",
    "myshopify.com",
    "cloudflare.com",
    "google.com",
    "beeketing.com",
    "klaviyo.com",
    "mailchimp.com",
    "gorgias.com",
    "zendesk.com",
    "shopifyemail.com",
    "email.myshopify.com",
}

# Patterns that look like emails but aren't useful
EMAIL_BLOCKLIST_SUBSTRINGS = (
    "noreply",
    "no-reply",
    "donotreply",
    "mailer-daemon",
    "webpack",
    "sentry",
    "example@",
    "@2x.",
    "@3x.",
    ".png",
    ".jpg",
)

OUTPUT_DIR = "output"
CSV_FILENAME = "shopify_leads.csv"
