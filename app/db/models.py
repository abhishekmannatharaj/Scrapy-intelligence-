"""Relational models: crawl jobs and normalized product records."""
import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    url: Mapped[str] = mapped_column(Text)
    spider: Mapped[str] = mapped_column(String(32), default="universal")
    max_pages: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.PENDING.value, index=True)
    items_scraped: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    products: Mapped[list["ProductRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True)


class ProductRecord(Base):
    __tablename__ = "product_records"
    __table_args__ = (
        UniqueConstraint("job_id", "url", name="uq_product_job_url"),
        Index("ix_product_domain_price", "source_domain", "price"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_domain: Mapped[str] = mapped_column(String(255), index=True)
    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[CrawlJob] = relationship(back_populates="products")
