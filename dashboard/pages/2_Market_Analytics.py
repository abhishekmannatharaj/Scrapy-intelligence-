"""Pandas-powered KPIs, price histograms, competitor comparison and exports."""
import os
import sys
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

root_dir = Path(__file__).resolve().parent.parent.parent
root_path = str(root_dir)
if root_path in sys.path:
        sys.path.remove(root_path)
sys.path.insert(0, root_path)

from app.services.analytics import (
    catalog_distribution,
    competitor_comparison,
    compute_kpis,
    price_distribution,
    products_to_frame,
)

API = os.getenv("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(page_title="Market Analytics", page_icon="📊", layout="wide")
st.title("📊 Market Analytics")


@st.cache_data(ttl=30, show_spinner="Loading catalog…")
def load_products(job_id: str | None, max_rows: int = 20_000) -> list[dict]:
    rows, offset = [], 0
    while offset < max_rows:
        params = {"limit": 500, "offset": offset, **({"job_id": job_id} if job_id else {})}
        r = httpx.get(f"{API}/products", params=params, timeout=60)
        r.raise_for_status()
        page = r.json()
        rows += page["items"]
        offset += 500
        if offset >= page["total"]:
            break
    return rows


try:
    jobs = httpx.get(f"{API}/jobs", params={"limit": 100}, timeout=15).json()["items"]
except httpx.HTTPError as exc:
    st.error(f"API unreachable: {exc}")
    st.stop()

with st.sidebar:
    st.header("Filters")
    options = {"All jobs": None, **{f"{j['url'][:40]} · {j['id'][:8]}": j["id"] for j in jobs}}
    job_id = options[st.selectbox("Crawl job", list(options))]

df = products_to_frame(load_products(job_id))
if df.empty:
    st.info("No products yet. Trigger a crawl first.")
    st.stop()

with st.sidebar:
    domains = st.multiselect("Source", sorted(df["source_domain"].dropna().unique()))
    cats = st.multiselect("Category", sorted(df["category"].unique()))
    if df["price"].notna().any():
        lo, hi = float(df["price"].min()), float(df["price"].max())
        price_range = st.slider("Price range", lo, hi, (lo, hi)) if lo < hi else (lo, hi)
    else:
        price_range = None
    only_stock = st.checkbox("In stock only")

if domains:
    df = df[df["source_domain"].isin(domains)]
if cats:
    df = df[df["category"].isin(cats)]
if price_range:
    df = df[df["price"].between(*price_range) | df["price"].isna()]
if only_stock:
    df = df[df["in_stock"]]

k = compute_kpis(df)
cols = st.columns(5)
cols[0].metric("Products", f"{k['total_products']:,}")
cols[1].metric("Avg price", f"{k['avg_price']:.2f}" if k["avg_price"] is not None else "—")
cols[2].metric("Median price", f"{k['median_price']:.2f}" if k["median_price"] is not None else "—")
cols[3].metric("In stock", f"{k['in_stock_rate']:.0%}" if k["in_stock_rate"] is not None else "—")
cols[4].metric("Avg rating", f"{k['avg_rating']:.2f}" if k["avg_rating"] is not None else "—")

left, right = st.columns(2)
with left:
    st.subheader("Price distribution")
    dist = pd.DataFrame(price_distribution(df))
    if not dist.empty:
        st.plotly_chart(px.bar(dist, x="range", y="count"), use_container_width=True)
with right:
    st.subheader("Catalog distribution")
    cat = pd.DataFrame(catalog_distribution(df))
    if not cat.empty:
        st.plotly_chart(px.bar(cat, x="products", y="category", orientation="h",
                               hover_data=["avg_price", "share"]), use_container_width=True)

st.subheader("Competitor comparison")
comp = pd.DataFrame(competitor_comparison(df))
if not comp.empty:
    st.dataframe(comp, use_container_width=True, hide_index=True)
    if len(comp) > 1:
        st.plotly_chart(px.bar(comp, x="source_domain", y="avg_price", color="price_index"),
                        use_container_width=True)

st.subheader("Products")
st.dataframe(df.drop(columns=["in_stock"]), use_container_width=True, hide_index=True)
c1, c2 = st.columns(2)
c1.download_button("⬇️ Export CSV", df.to_csv(index=False).encode(), "products.csv", "text/csv")
c2.download_button("⬇️ Export JSON", df.to_json(orient="records", date_format="iso"),
                   "products.json", "application/json")
