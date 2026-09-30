"""Celery crawl task.

Twisted's reactor cannot be restarted inside a long-lived worker process (and Celery prefork
children are daemonic), so each job runs `scrapy.crawler.CrawlerProcess` in a fresh interpreter
(this module's `__main__`). The Celery task supervises that process and records job state.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import CrawlJob, JobStatus, ProductRecord
from app.db.postgres import SyncSessionLocal
from app.tasks.celery_app import celery_app

ROOT = Path(__file__).resolve().parents[2]
CRAWLER_DIR = ROOT / "crawler"
SPIDERS = {"universal", "dynamic"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _update_job(job_id: str, **fields) -> None:
    with SyncSessionLocal() as s:
        job = s.get(CrawlJob, job_id)
        if job:
            for k, v in fields.items():
                setattr(job, k, v)
            s.commit()


def _count_items(job_id: str) -> int:
    with SyncSessionLocal() as s:
        return s.scalar(select(func.count()).select_from(ProductRecord)
                        .where(ProductRecord.job_id == job_id)) or 0


@celery_app.task(bind=True, name="crawl.run")
def run_crawl(self, job_id: str, url: str, spider: str = "universal", max_pages: int = 50) -> dict:
    if spider not in SPIDERS:
        _update_job(job_id, status=JobStatus.FAILED.value, finished_at=_now(),
                    error=f"Unknown spider '{spider}'")
        return {"job_id": job_id, "status": "failed"}

    _update_job(job_id, status=JobStatus.RUNNING.value, started_at=_now(),
                celery_task_id=self.request.id)
    cmd = [sys.executable, "-m", "app.tasks.crawl_tasks",
           "--job-id", job_id, "--url", url, "--spider", spider, "--max-pages", str(max_pages)]
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                              timeout=get_settings().crawl_timeout_seconds)
        items = _count_items(job_id)
        if proc.returncode == 0:
            _update_job(job_id, status=JobStatus.SUCCESS.value, items_scraped=items,
                        finished_at=_now())
        else:
            _update_job(job_id, status=JobStatus.FAILED.value, items_scraped=items,
                        finished_at=_now(), error=(proc.stderr or proc.stdout)[-2000:])
    except subprocess.TimeoutExpired:
        _update_job(job_id, status=JobStatus.FAILED.value, items_scraped=_count_items(job_id),
                    finished_at=_now(), error="Crawl timed out")
    except Exception as exc:  # noqa: BLE001
        _update_job(job_id, status=JobStatus.FAILED.value, finished_at=_now(), error=str(exc))
        raise
    return {"job_id": job_id, "status": "done"}


def _crawl_in_process(job_id: str, url: str, spider: str, max_pages: int) -> int:
    """Runs in a dedicated interpreter: owns the Twisted reactor for one crawl."""
    os.chdir(CRAWLER_DIR)
    sys.path.insert(0, str(CRAWLER_DIR))
    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "market_spider.settings")
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()
    settings.set("CLOSESPIDER_PAGECOUNT", max_pages)
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(spider)
    process.crawl(crawler, url=url, job_id=job_id, max_pages=max_pages)
    process.start()
    stats = crawler.stats.get_stats()
    scraped = stats.get("item_scraped_count", 0)
    print(f"RESULT items={scraped} reason={stats.get('finish_reason')}")
    return 0 if scraped > 0 else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--spider", default="universal", choices=sorted(SPIDERS))
    ap.add_argument("--max-pages", type=int, default=50)
    a = ap.parse_args()
    sys.exit(_crawl_in_process(a.job_id, a.url, a.spider, a.max_pages))
