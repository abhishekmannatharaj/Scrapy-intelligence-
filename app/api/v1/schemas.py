"""Pydantic v2 request/response models."""
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

T = TypeVar("T")


class JobCreate(BaseModel):
    url: HttpUrl
    spider: Literal["universal", "dynamic"] = "universal"
    max_pages: int = Field(50, ge=1, le=5000, description="Max pages fetched before stopping")


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    spider: str
    max_pages: int
    status: str
    items_scraped: int
    error: str | None = None
    celery_task_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | str | None = None
    job_id: str
    url: str
    title: str
    price: float | None = None
    currency: str | None = None
    availability: str | None = None
    rating: float | None = None
    category: str | None = None
    image_url: str | None = None
    description: str | None = None
    source_domain: str
    extraction_method: str | None = None
    scraped_at: datetime | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class AnalyticsOut(BaseModel):
    kpis: dict[str, Any]
    price_distribution: list[dict[str, Any]]
    catalog_distribution: list[dict[str, Any]]
    competitor_comparison: list[dict[str, Any]]
