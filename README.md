# Shopify Lead Finder

Local Python tool to find **Shopify stores** (especially in **Pakistan**), discover **emails**, estimate **traffic**, and **export CSV** — no paid APIs, no database.

---

## What it does

1. **Finds stores** via DuckDuckGo (`site:myshopify.com`, `site:.pk`, “powered by Shopify”, etc.)
2. **Verifies Shopify** using page fingerprints (`cdn.shopify.com`, `Shopify.theme`, …)
3. **Resolves custom domains** (`.com` / `.pk`) from `*.myshopify.com` redirects
4. **Finds emails** in 3 layers:
   - Search snippets
   - Contact / about / policy pages
   - Domain web search (own-domain emails only)
5. **Ranks traffic** with free estimates + a 0–100 score
6. **Dedupes** stores/emails so reruns don’t repeat leads
7. **Exports CSV / JSON** to `output/`

---

## Requirements

- Windows / macOS / Linux
- **Python 3.10+**
- Internet connection

---

## Setup

Open a terminal in this folder:

```bash
cd c:\Users\PC\Desktop\scraper
```

### 1. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Run the UI (recommended)

```bash
streamlit run ui_app.py
```

Then open **http://localhost:8501** in your browser.

### UI steps

1. Enter a **niche** (e.g. `clothing`, `skincare`, `jewelry`)
2. Keep **Country** on `Pakistan` (default)
3. Set **Max stores** (start with `5`–`10`)
4. Optional filters:
   - **Only rows with email** — drop stores with no email
   - **Skip previously scraped leads** — avoid duplicates (recommended)
   - **Loose location filter** — wider search, less strict Pakistan matching
   - **Min traffic score** — e.g. `40` for stronger stores
   - **Min monthly visits** — filter by free visit estimate
5. Click **Find leads**
6. Click **Export CSV** to download results

Results are also saved automatically under `output/`.

---

## Run from the command line

```bash
python main.py "clothing" -n 10 --country pakistan --with-email-only
```

### CLI options

| Flag | Meaning |
|------|---------|
| `"niche"` | Required. Search niche keywords |
| `-n` / `--max-stores` | How many stores to keep (default from config) |
| `-c` / `--country` | `pakistan` (default) or `global` |
| `--with-email-only` | Keep only leads that have an email |
| `--loose` | Less strict location matching |
| `--min-traffic` | Minimum `traffic_score` (0–100) |
| `--allow-duplicates` | Do **not** skip previously scraped stores |

### Examples

```bash
# Small Pakistan clothing batch
python main.py "clothing" -n 5 --country pakistan

# Only leads with email + traffic score 40+
python main.py "skincare" -n 15 --with-email-only --min-traffic 40

# Broader search (less strict Pakistan filter)
python main.py "jewelry" -n 10 --loose
```

---

## Output files

All exports go to the `output/` folder:

| File | Description |
|------|-------------|
| `pakistan_<niche>_shopify_leads.csv` | Main spreadsheet (Excel-friendly) |
| `pakistan_<niche>_YYYYMMDD_HHMMSS.json` | Full JSON dump |
| `seen_leads.json` | Dedupe memory (hosts + emails already scraped) |

### Useful CSV columns

| Column | Meaning |
|--------|---------|
| `store_url` | Best public store URL |
| `custom_domain` | Brand domain (`.com` / `.pk`) if found |
| `myshopify_url` | Original `*.myshopify.com` if known |
| `shopify_verified` | `True` only if Shopify proof was found |
| `shopify_proof` | Evidence (e.g. `cdn.shopify.com`) |
| `primary_email` | Best email (brand `.com` preferred) |
| `all_emails` | All emails found |
| `monthly_visits_est` | Free estimated monthly visitors |
| `traffic_score` | 0–100 popularity proxy |
| `traffic_tier` | `high` / `medium` / `low` |

---

## Project structure

```
scraper/
├── ui_app.py            # Streamlit UI
├── main.py              # CLI
├── pipeline.py          # End-to-end scrape flow
├── store_finder.py      # DuckDuckGo store discovery
├── domain_resolver.py   # Custom domain + Shopify verify
├── email_finder.py      # 3-layer email discovery
├── email_utils.py       # Clean / rank emails
├── traffic_rank.py      # Free traffic estimates + score
├── locations.py         # Pakistan / global targeting
├── cleaner.py           # Dedupe + CSV/JSON export
├── seen_leads.py        # Local duplicate memory
├── config.py            # Delays, paths, filters
├── requirements.txt
├── README.md
└── output/              # CSV / JSON results
```

---

## Tips for better results

- Start small (`-n 5`) to test a niche
- Use specific niches: `organic skincare`, `mens streetwear`, not just `shop`
- Prefer stores with **custom `.com` / `.pk`** domains for outreach
- Keep **Skip previously scraped leads** enabled
- Email discovery is the slow step — expect ~30–60s per store
- `monthly_visits_est` is a **free estimate**, not real Google Analytics
- Small / new stores often show `0` visits (no public estimate)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `streamlit` not found | Activate `.venv`, then `pip install -r requirements.txt` |
| No stores found | Broader niche, enable **Loose location filter**, or try `global` |
| No emails | Normal for some stores; try more stores / different niche |
| Same leads again | Delete `output/seen_leads.json` or use `--allow-duplicates` |
| Search failed / rate limit | Wait a bit and retry; reduce `-n` |
| Port 8501 in use | `streamlit run ui_app.py --server.port 8502` |

---

## Legal / ethics

- Only collects **publicly visible** contact info
- Use emails for lawful outreach only (CAN-SPAM / local rules, unsubscribe, honest intent)
- Be polite — the scraper already delays between requests

---

## License / use

Built for personal / agency lead generation on your own machine.  
No warranty — free data sources can change or block scrapers over time.
