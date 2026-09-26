"""Pure Pandas analytics engine.

No network or subprocess calls live here — only DataFrame loading, cleaning,
and KPI computation, so it can be unit-tested and reused outside FastAPI.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

STOPWORDS = {
    "the", "a", "an", "of", "and", "to", "in", "on", "for", "with", "is",
    "at", "by", "from", "as", "it", "its", "this", "that", "you", "your",
}

REQUIRED_COLUMNS = [
    "title", "price", "rating", "availability", "reviews", "category", "url", "scraped_at",
]


def load_products(path: str | Path) -> pd.DataFrame:
    """Read a JSONL crawl output into a cleaned DataFrame. Missing file -> empty frame."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    df = pd.DataFrame.from_records(records)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return clean_dataframe(df)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate, coerce types, and fill missing values with safe defaults."""
    df = df.copy()
    df = df.drop_duplicates(subset=["url"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["reviews"] = pd.to_numeric(df["reviews"], errors="coerce").fillna(0).astype(int)
    df["availability"] = pd.to_numeric(df["availability"], errors="coerce").fillna(0).astype(int)
    df["category"] = df["category"].fillna("Unknown")
    df["title"] = df["title"].fillna("")
    df = df.dropna(subset=["price"])
    return df.reset_index(drop=True)


def _top_keywords(titles: pd.Series, top_n: int = 10) -> dict[str, int]:
    words: list[str] = []
    for title in titles:
        tokens = re.findall(r"[a-zA-Z]{3,}", str(title).lower())
        words.extend(t for t in tokens if t not in STOPWORDS)
    return dict(Counter(words).most_common(top_n))


def compute_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """Summary KPIs + distributions used to power the dashboard's charts."""
    if df.empty:
        return {
            "total_products": 0,
            "avg_price": None,
            "median_price": None,
            "min_price": None,
            "max_price": None,
            "avg_rating": None,
            "avg_reviews": None,
            "total_reviews": 0,
            "rating_distribution": {},
            "category_breakdown": {},
            "avg_price_by_category": {},
            "top_keywords": {},
        }

    rating_dist = df["rating"].dropna().astype(int).value_counts().sort_index()
    category_counts = df["category"].value_counts()
    price_by_category = df.groupby("category")["price"].mean().round(2)

    return {
        "total_products": int(len(df)),
        "avg_price": round(float(df["price"].mean()), 2),
        "median_price": round(float(df["price"].median()), 2),
        "min_price": round(float(df["price"].min()), 2),
        "max_price": round(float(df["price"].max()), 2),
        "avg_rating": round(float(df["rating"].mean()), 2) if df["rating"].notna().any() else None,
        "avg_reviews": round(float(df["reviews"].mean()), 2),
        "total_reviews": int(df["reviews"].sum()),
        "rating_distribution": {str(k): int(v) for k, v in rating_dist.items()},
        "category_breakdown": {str(k): int(v) for k, v in category_counts.items()},
        "avg_price_by_category": {str(k): float(v) for k, v in price_by_category.items()},
        "top_keywords": _top_keywords(df["title"]),
    }


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
