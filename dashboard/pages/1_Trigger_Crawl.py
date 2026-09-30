"""Submit a URL to crawl and track the job live."""
import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000/api/v1")
TERMINAL = {"success", "failed"}

st.set_page_config(page_title="Trigger Crawl", page_icon="🕷️", layout="wide")
st.title("🕷️ Trigger Crawl")

with st.form("crawl"):
    url = st.text_input("Catalog or search-listing URL", "https://books.toscrape.com/")
    c1, c2 = st.columns(2)
    spider = c1.selectbox("Engine", ["universal", "dynamic"],
                          help="universal = fast HTTP; dynamic = headless Chromium for JS sites")
    max_pages = c2.number_input("Max pages", 1, 5000, 50)
    submitted = st.form_submit_button("Start crawl", type="primary")

if submitted:
    try:
        r = httpx.post(f"{API}/jobs", json={"url": url, "spider": spider,
                                            "max_pages": int(max_pages)}, timeout=30)
        r.raise_for_status()
        st.session_state["job_id"] = r.json()["id"]
        st.toast("Job queued")
    except httpx.HTTPError as exc:
        st.error(f"Could not submit job: {exc}")


@st.fragment(run_every=2)
def tracker():
    job_id = st.session_state.get("job_id")
    if not job_id:
        st.info("Submit a crawl to see live progress.")
        return
    try:
        job = httpx.get(f"{API}/jobs/{job_id}", timeout=15).json()
    except httpx.HTTPError as exc:
        st.warning(f"Status unavailable: {exc}")
        return
    st.subheader(f"Job `{job['id']}`")
    status = job["status"]
    progress = min(job["items_scraped"] / max(job["max_pages"], 1), 1.0)
    icon = {"pending": "⏳", "running": "🔄", "success": "✅", "failed": "❌"}[status]
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", f"{icon} {status}")
    c2.metric("Items stored", job["items_scraped"])
    c3.metric("Engine", job["spider"])
    if status == "running":
        st.progress(progress, text="Crawling…")
    if job.get("error"):
        st.error(job["error"])
    if status in TERMINAL:
        st.caption("Finished. Open **Market Analytics** to explore the results.")


tracker()

st.divider()
st.subheader("Recent jobs")
try:
    jobs = httpx.get(f"{API}/jobs", params={"limit": 15}, timeout=15).json()["items"]
    if jobs:
        st.dataframe(pd.DataFrame(jobs)[["id", "url", "spider", "status", "items_scraped",
                                         "created_at"]], use_container_width=True, hide_index=True)
except httpx.HTTPError:
    st.caption("Job history unavailable.")
