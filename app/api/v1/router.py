import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import analytics

router = APIRouter()

# app/api/v1/router.py -> parents[3] is the project root (where scrapy.cfg lives)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store. Swap for Redis/DB if this ever needs to survive a restart.
JOBS: dict[str, dict] = {}


class CrawlRequest(BaseModel):
    category: str = ""
    max_pages: int = 5


class CrawlResponse(BaseModel):
    job_id: str
    status: str
    output_file: str


def _slugify(text: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in text.strip().lower())
    return slug or "all"


@router.post("/crawl", response_model=CrawlResponse)
def trigger_crawl(payload: CrawlRequest):
    """Launches `scrapy crawl products` as a background subprocess and returns immediately."""
    job_id = uuid.uuid4().hex[:10]
    slug = _slugify(payload.category)
    output_file = DATA_DIR / f"{slug}_{job_id}.jsonl"

    cmd = [
        sys.executable, "-m", "scrapy", "crawl", "products",
        "-a", f"category={payload.category}",
        "-a", f"max_pages={payload.max_pages}",
        "-s", f"OUTPUT_FILE={output_file}",
        "-s", "LOG_LEVEL=WARNING",
    ]

    process = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    JOBS[job_id] = {
        "process": process,
        "status": "running",
        "output_file": str(output_file),
        "category": payload.category,
    }
    return CrawlResponse(job_id=job_id, status="running", output_file=str(output_file))


def _refresh_status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job_id")
    if job["status"] == "running":
        ret = job["process"].poll()
        if ret is not None:
            job["status"] = "completed" if ret == 0 else "failed"
            if ret != 0:
                job["error"] = job["process"].stderr.read().decode(errors="ignore")[-2000:]
    return job


@router.get("/crawl/{job_id}/status")
def crawl_status(job_id: str):
    job = _refresh_status(job_id)
    return {
        "job_id": job_id,
        "status": job["status"],
        "output_file": job["output_file"],
        "error": job.get("error"),
    }


@router.get("/jobs")
def list_jobs():
    return [
        {
            "job_id": jid,
            "status": j["status"],
            "category": j["category"],
            "output_file": j["output_file"],
        }
        for jid, j in JOBS.items()
    ]


def _load_df(job_id: Optional[str], file: Optional[str]):
    if job_id:
        job = _refresh_status(job_id)
        path = job["output_file"]
    elif file:
        path = file
    else:
        raise HTTPException(400, "Provide job_id or file")
    return analytics.load_products(path), path


@router.get("/products")
def get_products(job_id: Optional[str] = None, file: Optional[str] = None):
    df, _ = _load_df(job_id, file)
    return {"count": len(df), "products": df.to_dict(orient="records")}


@router.get("/analytics")
def get_analytics(job_id: Optional[str] = None, file: Optional[str] = None):
    df, _ = _load_df(job_id, file)
    return analytics.compute_kpis(df)


@router.get("/download")
def download_csv(job_id: Optional[str] = None, file: Optional[str] = None):
    df, path = _load_df(job_id, file)
    csv_bytes = analytics.to_csv_bytes(df)
    filename = Path(path).stem + ".csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
