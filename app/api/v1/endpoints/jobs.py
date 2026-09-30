"""Crawl job endpoints: trigger a crawl and track its status."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import JobCreate, JobOut, Page
from app.db.models import CrawlJob, JobStatus
from app.db.postgres import get_db
from app.tasks.crawl_tasks import run_crawl

router = APIRouter()


@router.post("", response_model=JobOut, status_code=202)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)) -> CrawlJob:
    job = CrawlJob(url=str(payload.url), spider=payload.spider, max_pages=payload.max_pages)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    try:
        # apply_async does blocking broker I/O; keep the event loop free.
        await asyncio.to_thread(
            run_crawl.apply_async, kwargs={"job_id": job.id, "url": job.url,
                                           "spider": job.spider, "max_pages": job.max_pages},
            task_id=job.id)
    except Exception as exc:  # broker unavailable
        job.status, job.error = JobStatus.FAILED.value, f"Queue unavailable: {exc}"
        await db.commit()
        raise HTTPException(503, "Task queue unavailable") from exc
    job.celery_task_id = job.id
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=Page[JobOut])
async def list_jobs(status: str | None = None, limit: int = Query(20, ge=1, le=200),
                    offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    q = select(CrawlJob)
    if status:
        q = q.where(CrawlJob.status == status)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = (await db.scalars(q.order_by(CrawlJob.created_at.desc()).limit(limit).offset(offset))).all()
    return Page[JobOut](items=rows, total=total or 0, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> CrawlJob:
    job = await db.get(CrawlJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
