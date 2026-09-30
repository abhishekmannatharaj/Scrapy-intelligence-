"""Pandas analytics pipeline: KPIs, price distribution, catalog mix, competitor comparison."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

COLUMNS = ["title", "price", "currency", "availability", "rating", "category",
           "source_domain", "url", "scraped_at", "job_id"]


def products_to_frame(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(records))
    for col in COLUMNS:
        if col not in df:
            df[col] = None
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["category"] = df["category"].fillna("Uncategorized")
    df["in_stock"] = df["availability"].fillna("").str.contains("in stock", case=False)
    return df


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) else round(float(value), 4)
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def compute_kpis(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total_products": 0, "distinct_domains": 0, "distinct_categories": 0,
                "priced_coverage": None, "avg_price": None, "median_price": None,
                "min_price": None, "max_price": None, "in_stock_rate": None, "avg_rating": None}
    price = df["price"].dropna()
    return _clean({
        "total_products": len(df),
        "distinct_domains": df["source_domain"].nunique(),
        "distinct_categories": df["category"].nunique(),
        "priced_coverage": len(price) / len(df),
        "avg_price": price.mean() if len(price) else None,
        "median_price": price.median() if len(price) else None,
        "min_price": price.min() if len(price) else None,
        "max_price": price.max() if len(price) else None,
        "in_stock_rate": df["in_stock"].mean(),
        "avg_rating": df["rating"].mean(),
    })


def price_distribution(df: pd.DataFrame, bins: int = 10) -> list[dict[str, Any]]:
    price = df["price"].dropna()
    if price.empty:
        return []
    if price.nunique() == 1:
        v = float(price.iloc[0])
        return [{"range": f"{v:.2f}", "lower": v, "upper": v, "count": int(len(price))}]
    cut = pd.cut(price, bins=bins)
    counts = cut.value_counts(sort=False)
    return _clean([{"range": f"{iv.left:.2f} – {iv.right:.2f}", "lower": iv.left,
                    "upper": iv.right, "count": int(n)} for iv, n in counts.items()])


def catalog_distribution(df: pd.DataFrame, top_n: int = 15) -> list[dict[str, Any]]:
    if df.empty:
        return []
    g = (df.groupby("category").agg(products=("url", "count"), avg_price=("price", "mean"))
         .sort_values("products", ascending=False).head(top_n).reset_index())
    g["share"] = g["products"] / len(df)
    return _clean(g.to_dict("records"))


def competitor_comparison(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    overall = df["price"].mean()
    g = df.groupby("source_domain").agg(
        products=("url", "count"), avg_price=("price", "mean"), median_price=("price", "median"),
        min_price=("price", "min"), max_price=("price", "max"),
        in_stock_rate=("in_stock", "mean"), avg_rating=("rating", "mean")).reset_index()
    g["price_index"] = g["avg_price"] / overall * 100 if overall and not pd.isna(overall) else None
    return _clean(g.sort_values("products", ascending=False).to_dict("records"))


def build_report(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "kpis": compute_kpis(df),
        "price_distribution": price_distribution(df),
        "catalog_distribution": catalog_distribution(df),
        "competitor_comparison": competitor_comparison(df),
    }
