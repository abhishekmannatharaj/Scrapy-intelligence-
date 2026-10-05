import os
import time

import pandas as pd
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")


def _request_json(method, url, **kwargs):
    response = requests.request(method, url, timeout=10, **kwargs)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Competitor Intelligence Dashboard", layout="wide")
st.title("🛒 E-Commerce Competitor Intelligence Dashboard")

if "job_id" not in st.session_state:
    st.session_state.job_id = None

with st.sidebar:
    st.header("Crawl Controls")
    category = st.text_input("Category (e.g. travel, mystery, fiction)", value="travel")
    max_pages = st.slider("Max pages per category", 1, 10, 3)
    run_crawl = st.button("🔍 Run Crawl", use_container_width=True)

    st.divider()
    st.caption("Or inspect a previous job")
    manual_job_id = st.text_input("Existing Job ID", value="")
    if st.button("Load Job", use_container_width=True) and manual_job_id:
        st.session_state.job_id = manual_job_id

if run_crawl:
    try:
        result = _request_json(
            "POST",
            f"{API_BASE}/crawl",
            json={"category": category, "max_pages": max_pages},
        )
        st.session_state.job_id = result["job_id"]
        st.success(f"Crawl started — job {st.session_state.job_id}")
    except requests.RequestException as exc:
        st.error(f"Could not reach the API: {exc}")
    except (KeyError, ValueError) as exc:
        st.error(f"The API returned an invalid crawl response: {exc}")

job_id = st.session_state.job_id

if job_id:
    status_placeholder = st.empty()
    status = "running"
    job_error = None
    with st.spinner("Crawling and processing..."):
        while status == "running":
            try:
                status_result = _request_json(
                    "GET", f"{API_BASE}/crawl/{job_id}/status"
                )
                status = status_result["status"]
                job_error = status_result.get("error")
            except requests.RequestException as exc:
                st.error(f"Status check failed: {exc}")
                status = "error"
                break
            except (KeyError, ValueError) as exc:
                st.error(f"The API returned an invalid job status: {exc}")
                status = "error"
                break
            if status == "running":
                time.sleep(1.5)

    if status == "failed":
        st.error(job_error or f"Crawl failed for job {job_id}. Check backend logs.")
    elif status == "completed":
        status_placeholder.success(f"Job {job_id} completed ✅")

        try:
            kpis = _request_json(
                "GET", f"{API_BASE}/analytics", params={"job_id": job_id}
            )
            products_result = _request_json(
                "GET", f"{API_BASE}/products", params={"job_id": job_id}
            )
            products = products_result["products"]
        except requests.RequestException as exc:
            st.error(f"Could not load crawl results: {exc}")
            st.stop()
        except (KeyError, ValueError) as exc:
            st.error(f"The API returned invalid crawl results: {exc}")
            st.stop()

        df = pd.DataFrame(products)

        if df.empty:
            st.warning("No products were scraped for this category. Try a different keyword.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Products", kpis["total_products"])
            c2.metric("Avg Price", f"${kpis['avg_price']:.2f}" if kpis["avg_price"] else "—")
            c3.metric("Avg Rating", f"{kpis['avg_rating']:.2f} ⭐" if kpis["avg_rating"] else "—")
            c4.metric("Avg Reviews", kpis["avg_reviews"])

            col_left, col_right = st.columns(2)
            with col_left:
                st.subheader("Price Distribution")
                st.bar_chart(df["price"])
                st.subheader("Rating Distribution")
                st.bar_chart(pd.Series(kpis["rating_distribution"]).sort_index())
            with col_right:
                st.subheader("Avg Price by Category")
                st.bar_chart(pd.Series(kpis["avg_price_by_category"]))
                st.subheader("Top Keywords in Titles")
                st.bar_chart(pd.Series(kpis["top_keywords"]))

            st.subheader("Product Catalog")
            price_min, price_max = float(df["price"].min()), float(df["price"].max())
            if price_min == price_max:
                price_max += 0.01
            price_range = st.slider("Filter by price", price_min, price_max, (price_min, price_max))
            filtered = df[(df["price"] >= price_range[0]) & (df["price"] <= price_range[1])]
            st.dataframe(filtered, use_container_width=True)

            csv_bytes = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV",
                data=csv_bytes,
                file_name=f"competitor_products_{job_id}.csv",
                mime="text/csv",
            )
    elif status != "error":
        st.error(f"The API returned an unexpected crawl status: {status}")
else:
    st.info("Enter a category and click **Run Crawl** to get started.")
