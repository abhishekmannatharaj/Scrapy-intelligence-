from app.services.analytics import build_report, products_to_frame

ROWS = [
    {"title": "a", "price": 10, "availability": "In stock", "rating": 4, "category": "X",
     "source_domain": "s1.com", "url": "u1", "job_id": "j"},
    {"title": "b", "price": 30, "availability": "Out of stock", "rating": 2, "category": "Y",
     "source_domain": "s2.com", "url": "u2", "job_id": "j"},
    {"title": "c", "price": None, "availability": None, "rating": None, "category": None,
     "source_domain": "s2.com", "url": "u3", "job_id": "j"},
]


def test_report_shapes():
    r = build_report(products_to_frame(ROWS))
    assert r["kpis"]["total_products"] == 3
    assert r["kpis"]["avg_price"] == 20.0
    assert r["kpis"]["in_stock_rate"] == round(1 / 3, 4)
    assert sum(b["count"] for b in r["price_distribution"]) == 2
    assert {c["category"] for c in r["catalog_distribution"]} == {"X", "Y", "Uncategorized"}
    assert {c["source_domain"] for c in r["competitor_comparison"]} == {"s1.com", "s2.com"}


def test_empty_frame():
    r = build_report(products_to_frame([]))
    assert r["kpis"]["total_products"] == 0 and r["price_distribution"] == []
