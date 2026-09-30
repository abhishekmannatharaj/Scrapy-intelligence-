"""Product query + analytics endpoints (PostgreSQL by default, MongoDB optional)."""
import asyncio
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import AnalyticsOut, Page, ProductOut
from app.db.models import ProductRecord
from app.db.mongo import get_products_collection
from app.db.postgres import get_db
from app.services.analytics import build_report, products_to_frame

router = APIRouter()

SORTS = {"price", "-price", "title", "-title", "scraped_at", "-scraped_at"}
_STOCK = "%in stock%"


def _order(sort: str):
    col = getattr(ProductRecord, sort.lstrip("-"))
    return col.desc() if sort.startswith("-") else col.asc()


def _pg_filters(q, job_id, domain, category, search, min_price, max_price, in_stock):
    if job_id:
        q = q.where(ProductRecord.job_id == job_id)
    if domain:
        q = q.where(ProductRecord.source_domain == domain)
    if category:
        q = q.where(ProductRecord.category == category)
    if search:
        q = q.where(ProductRecord.title.ilike(f"%{search}%"))
    if min_price is not None:
        q = q.where(ProductRecord.price >= min_price)
    if max_price is not None:
        q = q.where(ProductRecord.price <= max_price)
    if in_stock is True:
        q = q.where(ProductRecord.availability.ilike(_STOCK))
    elif in_stock is False:
        q = q.where(~func.coalesce(ProductRecord.availability, "").ilike(_STOCK))
    return q


@router.get("", response_model=Page[ProductOut])
async def list_products(
    job_id: str | None = None, domain: str | None = None, category: str | None = None,
    q: str | None = Query(None, description="Title substring"),
    min_price: float | None = Query(None, ge=0), max_price: float | None = Query(None, ge=0),
    in_stock: bool | None = None,
    source: Literal["postgres", "mongo"] = "postgres",
    sort: str = "-scraped_at",
    limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    sort = sort if sort in SORTS else "-scraped_at"
    if source == "mongo":
        return await _list_mongo(job_id, domain, category, q, min_price, max_price,
                                 in_stock, sort, limit, offset)
    base = _pg_filters(select(ProductRecord), job_id, domain, category, q,
                       min_price, max_price, in_stock)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (await db.scalars(base.order_by(_order(sort)).limit(limit).offset(offset))).all()
    return Page[ProductOut](items=rows, total=total or 0, limit=limit, offset=offset)


async def _list_mongo(job_id, domain, category, q, min_price, max_price, in_stock,
                      sort, limit, offset) -> Page[ProductOut]:
    flt: dict = {}
    for key, val in (("job_id", job_id), ("source_domain", domain), ("category", category)):
        if val:
            flt[key] = val
    if q:
        flt["title"] = {"$regex": re.escape(q), "$options": "i"}
    if min_price is not None or max_price is not None:
        flt["price"] = {**({"$gte": min_price} if min_price is not None else {}),
                        **({"$lte": max_price} if max_price is not None else {})}
    if in_stock is not None:
        rx = {"$regex": "in stock", "$options": "i"}
        flt["availability"] = rx if in_stock else {"$not": {"$regex": "in stock", "$options": "i"}}
    col = get_products_collection()
    total = await col.count_documents(flt)
    cursor = (col.find(flt).sort(sort.lstrip("-"), -1 if sort.startswith("-") else 1)
              .skip(offset).limit(limit))
    items = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        items.append(ProductOut.model_validate(doc))
    return Page[ProductOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(job_id: str | None = None, domain: str | None = None,
                    db: AsyncSession = Depends(get_db)):
    q = _pg_filters(select(ProductRecord.title, ProductRecord.price, ProductRecord.currency,
                           ProductRecord.availability, ProductRecord.rating,
                           ProductRecord.category, ProductRecord.source_domain,
                           ProductRecord.url, ProductRecord.job_id),
                    job_id, domain, None, None, None, None, None).limit(100_000)
    rows = [dict(r._mapping) for r in (await db.execute(q)).all()]
    # Pandas is CPU-bound: run off the event loop.
    return await asyncio.to_thread(lambda: build_report(products_to_frame(rows)))
