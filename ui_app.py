"""
Local Streamlit UI — no database required.

Run:
  streamlit run ui_app.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from cleaner import summary_stats
from locations import LOCATIONS
from pipeline import run_scrape

st.set_page_config(
    page_title="Shopify Lead Finder",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Source+Sans+3:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --ink: #142033; --muted: #667788; --paper: #eef2f0; --panel: #ffffff;
  --line: #d5dde3; --accent: #0b7a5c; --accent-dark: #086049;
  --accent-soft: #e3f5ef; --amber: #b45309; --amber-soft: #fff7ed;
  --sky: #0369a1; --sky-soft: #e0f2fe;
}
html, body, .stApp { font-family: "Source Sans 3", sans-serif; color: var(--ink); }
.stApp { background: linear-gradient(180deg, #e8f0ec 0%, var(--paper) 28%, #e9edf0 100%); }
section[data-testid="stSidebar"] { background: #fbfcfc !important; border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  color: var(--ink) !important;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] [data-baseweb="input"] {
  background: #fff !important; color: var(--ink) !important; border-color: var(--line) !important;
}
h1, .brand-title {
  font-family: "Fraunces", Georgia, serif !important; letter-spacing: -0.025em; color: var(--ink) !important;
}
.hero {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 1.5rem;
  padding: 0.25rem 0 1.4rem; border-bottom: 1px solid var(--line); margin-bottom: 1.35rem;
}
.brand-mark {
  display: inline-flex; align-items: center; justify-content: center; width: 2.2rem; height: 2.2rem;
  border-radius: 0.55rem; background: var(--accent); color: #fff; margin-right: 0.65rem;
}
.brand-title { font-size: 2.15rem; font-weight: 700; margin: 0; display: inline; }
.brand-sub { color: var(--muted); font-size: 1.02rem; max-width: 36rem; margin: 0.55rem 0 0; }
.hero-pills { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.pill {
  font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; padding: 0.28rem 0.55rem;
  border-radius: 999px; background: var(--panel); border: 1px solid var(--line); color: var(--muted);
}
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.7rem; margin: 0.35rem 0 1.25rem; }
@media (max-width: 1100px) { .stat-row { grid-template-columns: repeat(3, 1fr); } }
.stat {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.95rem 1rem;
}
.stat .label {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); font-weight: 600;
}
.stat .value { font-family: "IBM Plex Mono", monospace; font-size: 1.55rem; margin-top: 0.25rem; }
.stat .hint { font-size: 0.78rem; color: var(--muted); margin-top: 0.2rem; }
.lead-card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 1rem 1.15rem;
  display: grid; grid-template-columns: 1.4fr 1fr 1.1fr; gap: 1rem; margin-bottom: 0.7rem;
}
@media (max-width: 900px) { .lead-card { grid-template-columns: 1fr; } }
.lead-name { font-family: "Fraunces", Georgia, serif; font-size: 1.15rem; font-weight: 600; margin: 0 0 0.25rem; }
.lead-url a { color: var(--accent-dark); text-decoration: none; font-size: 0.88rem; word-break: break-all; }
.lead-meta { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.55rem; }
.badge { font-family: "IBM Plex Mono", monospace; font-size: 0.68rem; padding: 0.2rem 0.45rem; border-radius: 6px; }
.badge-high { background: var(--accent-soft); color: var(--accent-dark); }
.badge-medium { background: var(--amber-soft); color: var(--amber); }
.badge-low { background: #f1f5f9; color: #64748b; }
.badge-ok { background: var(--sky-soft); color: var(--sky); }
.badge-muted { background: #f8fafc; color: var(--muted); border: 1px solid var(--line); }
.metric-block .k {
  font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); font-weight: 600;
}
.metric-block .v { font-family: "IBM Plex Mono", monospace; font-size: 1.05rem; margin-top: 0.15rem; }
.email-main { font-family: "IBM Plex Mono", monospace; font-size: 0.95rem; word-break: break-all; }
.email-sub { margin-top: 0.35rem; font-size: 0.8rem; color: var(--muted); word-break: break-all; }
.status-chip {
  display: inline-block; background: var(--accent-soft); color: var(--accent-dark);
  font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; padding: 0.3rem 0.6rem; border-radius: 8px;
}
.section-label {
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted); font-weight: 700; margin: 0.4rem 0 0.65rem;
}
.empty-panel {
  background: var(--panel); border: 1px dashed #c5d0d8; border-radius: 16px;
  padding: 2.4rem 1.75rem; text-align: center;
}
.stButton > button {
  background: var(--accent) !important; color: #fff !important; border: none !important; border-radius: 10px !important;
}
.stDownloadButton > button {
  background: #fff !important; color: var(--ink) !important; border: 1px solid var(--line) !important;
  border-radius: 10px !important; font-weight: 600 !important;
}
"""


def fmt_num(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "—"
    if n <= 0:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def tier_class(tier: str) -> str:
    t = (tier or "low").lower()
    if t == "high":
        return "badge-high"
    if t == "medium":
        return "badge-medium"
    return "badge-low"


def lead_card_html(lead: dict, rank: int) -> str:
    title = (lead.get("title") or lead.get("store_url") or "Store").strip()
    if len(title) > 64:
        title = title[:61] + "…"
    url = lead.get("custom_domain") or lead.get("store_url") or "#"
    email = lead.get("primary_email") or "—"
    extras = lead.get("all_emails") or ""
    tier = (lead.get("traffic_tier") or "low").lower()
    badges = [
        f'<span class="badge {tier_class(tier)}">{tier.upper()} TRAFFIC</span>',
        f'<span class="badge badge-muted">#{rank}</span>',
    ]
    if lead.get("shopify_verified"):
        badges.append('<span class="badge badge-ok">SHOPIFY ✓</span>')
    if lead.get("currency_hint"):
        badges.append(f'<span class="badge badge-muted">{lead["currency_hint"]}</span>')
    extra = ""
    if extras and extras != email:
        extra = f'<div class="email-sub">{extras}</div>'
    return f"""
    <div class="lead-card">
      <div>
        <div class="lead-name">{title}</div>
        <div class="lead-url"><a href="{url}" target="_blank" rel="noopener">{url}</a></div>
        <div class="lead-meta">{"".join(badges)}</div>
      </div>
      <div>
        <div class="metric-block" style="margin-bottom:0.65rem">
          <div class="k">Est. monthly visits</div>
          <div class="v">{fmt_num(lead.get("monthly_visits_est"))}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
          <div class="metric-block"><div class="k">Score</div><div class="v">{lead.get("traffic_score") or 0}</div></div>
          <div class="metric-block"><div class="k">Products</div><div class="v">{lead.get("product_count") or "—"}</div></div>
        </div>
      </div>
      <div>
        <div class="metric-block" style="margin-bottom:0.35rem"><div class="k">Primary email</div></div>
        <div class="email-main">{email}</div>{extra}
      </div>
    </div>
    """


def leads_csv_bytes(leads: list[dict]) -> bytes:
    if not leads:
        return b""
    buf = io.StringIO()
    pd.DataFrame(leads).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero">
      <div>
        <div><span class="brand-mark">◈</span><h1 class="brand-title">Shopify Lead Finder</h1></div>
        <p class="brand-sub">
          Local tool — find Pakistan Shopify stores, emails, and free traffic estimates.
          Results save to the <b>output/</b> folder as CSV.
        </p>
      </div>
      <div class="hero-pills">
        <span class="pill">local only</span>
        <span class="pill">CSV export</span>
        <span class="pill">no database</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("#### Run settings")
    niche = st.text_input("Niche", value="clothing", placeholder="clothing, skincare…")
    country = st.selectbox(
        "Country",
        options=sorted(LOCATIONS.keys()),
        index=sorted(LOCATIONS.keys()).index("pakistan")
        if "pakistan" in LOCATIONS
        else 0,
        format_func=lambda k: LOCATIONS[k]["label"],
    )
    max_stores = st.slider("Max stores", 3, 50, 8, 1)
    st.markdown("#### Filters")
    with_email_only = st.checkbox("Only rows with email", value=True)
    skip_seen = st.checkbox("Skip previously scraped leads", value=True)
    loose = st.checkbox("Loose location filter", value=False)
    min_traffic = st.slider("Min traffic score", 0, 80, 0, 5)
    min_visits = st.number_input("Min monthly visits (est.)", min_value=0, value=0, step=500)
    st.caption("Tip: start with 5–10 stores.")
    run = st.button("Find leads", type="primary", use_container_width=True)

if "result" not in st.session_state:
    st.session_state.result = None

if run:
    if not niche.strip():
        st.error("Enter a niche first.")
    else:
        progress = st.progress(0.0, text="Starting…")
        status = st.empty()

        def on_progress(stage: str, pct: float, extra=None) -> None:
            progress.progress(min(max(pct, 0.0), 1.0), text=stage)
            status.markdown(
                f'<span class="status-chip">{stage}</span>',
                unsafe_allow_html=True,
            )

        try:
            result = run_scrape(
                niche.strip(),
                max_stores=max_stores,
                country=country,
                with_email_only=with_email_only,
                loose=loose,
                min_traffic_score=min_traffic,
                skip_seen=skip_seen,
                on_progress=on_progress,
            )
            if min_visits and result.get("leads"):
                result = dict(result)
                result["leads"] = [
                    L
                    for L in result["leads"]
                    if int(L.get("monthly_visits_est") or 0) >= int(min_visits)
                ]
                result["stats"] = summary_stats(result["leads"])
            st.session_state.result = result
            st.session_state.last_niche = niche.strip()
            st.session_state.last_country = country
        except Exception as exc:
            st.session_state.result = None
            st.error(f"Scrape failed: {exc}")

        progress.progress(1.0, text="Done")
        status.markdown('<span class="status-chip">Done</span>', unsafe_allow_html=True)

result = st.session_state.result

if result is None:
    st.markdown(
        """
        <div class="empty-panel">
          <h3>Ready when you are</h3>
          <p>Set a niche in the sidebar and click <b>Find leads</b>. Export CSV when done.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    leads = list(result.get("leads") or [])
    stats = result["stats"]
    visits_known = sum(1 for L in leads if int(L.get("monthly_visits_est") or 0) > 0)
    top_visits = max((int(L.get("monthly_visits_est") or 0) for L in leads), default=0)

    st.markdown(
        f"""
        <div class="stat-row">
          <div class="stat"><div class="label">Stores</div><div class="value">{stats['total_stores']}</div></div>
          <div class="stat"><div class="label">With email</div><div class="value">{stats['with_email']}</div>
            <div class="hint">{stats['discovery_rate_pct']}% discovery</div></div>
          <div class="stat"><div class="label">Custom domains</div>
            <div class="value">{result.get('custom_domain_count', 0)}</div></div>
          <div class="stat"><div class="label">Traffic data</div><div class="value">{visits_known}</div></div>
          <div class="stat"><div class="label">Top monthly visits</div>
            <div class="value">{fmt_num(top_visits)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Export row — always visible when there are leads
    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    csv_bytes = leads_csv_bytes(leads)
    csv_path = result.get("csv_path")
    file_name = (
        Path(csv_path).name
        if csv_path
        else f"{country}_{st.session_state.get('last_niche', 'leads')}_shopify_leads.csv"
    )

    with c1:
        st.download_button(
            "⬇ Export CSV",
            data=csv_bytes,
            file_name=file_name,
            mime="text/csv",
            type="primary",
            use_container_width=True,
            disabled=not bool(leads),
        )
    with c2:
        json_path = result.get("json_path")
        if json_path and Path(json_path).exists():
            st.download_button(
                "Export JSON",
                data=Path(json_path).read_bytes(),
                file_name=Path(json_path).name,
                mime="application/json",
                use_container_width=True,
            )
    with c3:
        if csv_path:
            st.caption(f"Also saved on disk: `{csv_path}`")
        st.caption(f"Skipped duplicates: {result.get('skipped_duplicates', 0)}")

    if not leads:
        st.warning("No stores matched. Try a broader niche or turn off skip-seen.")
    else:
        view = st.radio("View", ["Cards", "Table"], horizontal=True, label_visibility="collapsed")
        st.markdown(
            '<div class="section-label">Leads · sorted by estimated traffic</div>',
            unsafe_allow_html=True,
        )
        if view == "Cards":
            html = "".join(lead_card_html(L, i + 1) for i, L in enumerate(leads[:40]))
            st.markdown(html, unsafe_allow_html=True)
        else:
            df = pd.DataFrame(leads)
            cols = [
                c
                for c in [
                    "title",
                    "store_url",
                    "custom_domain",
                    "primary_email",
                    "monthly_visits_est",
                    "traffic_score",
                    "traffic_tier",
                    "shopify_verified",
                    "currency_hint",
                ]
                if c in df.columns
            ]
            st.dataframe(df[cols], use_container_width=True, hide_index=True, height=480)

        st.download_button(
            "⬇ Export CSV again",
            data=csv_bytes,
            file_name=file_name,
            mime="text/csv",
            use_container_width=False,
        )
