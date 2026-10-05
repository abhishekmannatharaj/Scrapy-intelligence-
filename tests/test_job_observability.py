import asyncio
from datetime import datetime, timedelta, timezone

from app.api.v1.endpoints.jobs import summarize_jobs
from app.api.v1.schemas import JobOut


def make_job(*, started_at=None, finished_at=None):
    return JobOut(
        id="job-1",
        url="https://shop.test/",
        spider="universal",
        max_pages=10,
        status="success",
        items_scraped=4,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        started_at=started_at,
        finished_at=finished_at,
    )


def test_job_duration_is_none_before_start():
    assert make_job().duration_seconds is None


def test_completed_job_exposes_duration_seconds():
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    job = make_job(started_at=started_at, finished_at=started_at + timedelta(seconds=12.345))
    assert job.duration_seconds == 12.35
    assert job.model_dump()["duration_seconds"] == 12.35


def test_job_summary_counts_known_statuses():
    class Result:
        def all(self):
            return [("pending", 2), ("running", 1), ("success", 5), ("failed", 3)]

    class Database:
        async def execute(self, statement):
            return Result()

    summary = asyncio.run(summarize_jobs(Database()))
    assert summary.model_dump() == {
        "total_jobs": 11,
        "pending": 2,
        "running": 1,
        "success": 5,
        "failed": 3,
    }
