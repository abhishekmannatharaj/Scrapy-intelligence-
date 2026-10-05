"""Streamlit executive dashboard: landing page (multi-page nav lives in dashboard/pages)."""
import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(page_title="Market Pulse", page_icon="📈", layout="wide")
st.title("📈 Market Pulse")
st.caption("Market intelligence and crawl operations, at a glance.")

with st.sidebar:
    st.header("Navigation")
    st.page_link("pages/1_Trigger_Crawl.py", label="Trigger crawl", icon="🕷️")
    st.page_link("pages/2_Market_Analytics.py", label="Market analytics", icon="📊")
    st.divider()
    st.caption(f"API: `{API}`")


@st.cache_data(ttl=15)
def fetch(path: str, **params):
    r = httpx.get(f"{API}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


try:
    report = fetch("/products/analytics")
    jobs = fetch("/jobs", limit=10)
    summary = fetch("/jobs/summary")
    failed_jobs = fetch("/jobs", status="failed", limit=5)
except httpx.HTTPError as exc:
    st.error(f"API unreachable: {exc}")
    st.stop()

st.subheader("Crawl operations")
job_cols = st.columns(5)
job_cols[0].metric("All jobs", f"{summary['total_jobs']:,}")
job_cols[1].metric("Running", summary["running"])
job_cols[2].metric("Queued", summary["pending"])
job_cols[3].metric("Completed", summary["success"])
job_cols[4].metric("Failed", summary["failed"])

if failed_jobs["items"]:
    with st.expander(f"Recent failures ({failed_jobs['total']})", expanded=True):
        for index, job in enumerate(failed_jobs["items"]):
            st.markdown(f"**{job['url']}** · `{job['id'][:8]}`")
            st.caption(f"Engine: {job['spider']} · Items stored: {job['items_scraped']}")
            st.error(job["error"] or "The worker marked this crawl as failed without an error message.")
            if index < len(failed_jobs["items"]) - 1:
                st.divider()

st.divider()
st.subheader("Catalog overview")
k = report["kpis"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Products tracked", f"{k['total_products']:,}")
c2.metric("Sources", k["distinct_domains"])
c3.metric("Avg price", f"{k['avg_price']:.2f}" if k["avg_price"] is not None else "—")
c4.metric("In stock", f"{k['in_stock_rate']:.0%}" if k["in_stock_rate"] is not None else "—")

st.subheader("Recent crawl jobs")
if jobs["items"]:
    df = pd.DataFrame(jobs["items"])[["id", "url", "spider", "status", "items_scraped",
                                      "duration_seconds", "created_at"]]
    df["id"] = df["id"].str[:8]
    df["duration_seconds"] = df["duration_seconds"].map(
        lambda value: f"{value:.1f}s" if pd.notna(value) else "—")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No crawls yet. Start one from **Trigger crawl**.")
