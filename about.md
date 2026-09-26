# Project Guide

## Overview

This project demonstrates an end-to-end competitor intelligence data workflow:

1. A user starts a crawl from the Streamlit dashboard or calls the FastAPI endpoint.
2. FastAPI launches the Scrapy spider as a background process and gives the request a job ID.
3. The spider discovers categories and product pages on Books to Scrape.
4. Scrapy pipelines validate and normalize each scraped product, then write it to a JSON Lines file.
5. The dashboard polls the API until the crawl finishes, then requests product records and Pandas-computed KPIs.
6. The dashboard displays metrics and charts, supports a price filter, and exports the filtered table to CSV.

The site's book catalog acts as a stand-in e-commerce dataset. The application is not integrated with a commercial marketplace, and its metrics should be interpreted as an example of the workflow rather than as live market intelligence.

## Complete File Structure

```text
competitor_intelligence_dashboard/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py
│   └── services/
│       ├── __init__.py
│       └── analytics.py
├── data/
│   └── raw/
│       ├── .gitkeep
│       ├── fiction_075f7846a6.jsonl
│       ├── mystery_95a650acae.jsonl
│       ├── travel_28b4c2e07b.jsonl
│       └── travel_6609d43904.jsonl
├── scraper/
│   ├── __init__.py
│   ├── items.py
│   ├── pipelines.py
│   ├── settings.py
│   └── spiders/
│       ├── __init__.py
│       └── product_spider.py
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── scrapy.cfg
└── streamlit_app.py
```

Runtime-created crawl files also go into `data/raw/`, with names based on the category and generated job ID. They are not all listed above because their names are created when crawls run.

## File Responsibilities

### Application and API

- `app/main.py` creates the FastAPI application, sets its title and version, enables CORS, mounts the v1 router at `/api/v1`, and exposes `/health`.
- `app/api/v1/router.py` defines crawl request/response models and HTTP routes. It constructs a Scrapy subprocess, keeps job metadata in the process-local `JOBS` dictionary, checks subprocess status, and delegates product loading and analysis to the analytics service.
- `app/services/analytics.py` owns JSONL loading, DataFrame cleanup, KPI calculations, keyword extraction, and CSV serialization. It has no network or subprocess responsibilities.
- The `__init__.py` files mark the application, API version, and service folders as Python packages.

### Scraper

- `scrapy.cfg` tells Scrapy to load settings from `scraper.settings`.
- `scraper/spiders/product_spider.py` starts at the catalog home page, filters category links by a case-insensitive substring when a category is given, follows listing pagination up to `max_pages` for each matched category, and visits each product detail page.
- `scraper/items.py` defines `ProductItem`. The spider initially fills raw text fields such as `price_raw` and `rating_raw`; the pipeline replaces these with normalized fields.
- `scraper/pipelines.py` contains two ordered pipelines. `CleaningPipeline` drops products without a title or parseable price and converts rating, price, stock availability, and review count to numeric values. `JsonWriterPipeline` writes one JSON object per line to the configured `OUTPUT_FILE`.
- `scraper/settings.py` sets the spider modules, polite crawl behavior, retries, AutoThrottle, pipeline order, and default output path (`data/raw/products.jsonl`). The API overrides the output path for each job.
- `scraper/__init__.py` and `scraper/spiders/__init__.py` are package markers.

### Dashboard and Data

- `streamlit_app.py` provides category and page controls, submits crawl requests, polls job status, displays KPIs and charts, filters the product table by price, and creates a CSV download.
- `data/raw/*.jsonl` contains sample crawl outputs. `.gitkeep` keeps the otherwise-empty output directory in version control.
- `.gitignore` excludes local/generated files as configured by the project.
- `pyproject.toml` declares project metadata, Python `>=3.11`, and pinned dependencies. `requirements.txt` repeats the pins for standard pip installation.

## Architecture and Workflow

```text
Streamlit UI
    | POST /api/v1/crawl
    v
FastAPI router -- launches --> Scrapy process
    |                              |
    | polls status                 | spider requests catalog/listing/detail pages
    |                              v
    |                       CleaningPipeline
    |                              |
    |                       JsonWriterPipeline
    |                              v
    |                       data/raw/<category>_<job-id>.jsonl
    |
    | GET products / analytics    |
    v                              v
Pandas analytics service <--- JSONL output
    |
    v
Dashboard metrics, charts, filtered table, CSV export
```

### Crawl Lifecycle

The dashboard sends a JSON payload to `POST /api/v1/crawl`. The router creates a short job ID and a filename such as `data/raw/travel_a1b2c3d4e5.jsonl`, then invokes the current Python interpreter with `-m scrapy crawl products`. This ensures the subprocess uses the same environment as the API.

The job response is returned immediately with status `running`. The dashboard polls `GET /api/v1/crawl/{job_id}/status`; when the process exits, the router reports `completed` or `failed`. A failed job response can include the tail of captured stderr.

`JOBS` lives only in API process memory. Consequently, status lookup and job IDs do not survive an API restart. The crawl output files are ordinary files and remain on disk.

### Spider and Pipeline Logic

The spider extracts category names from the sidebar. A non-empty category argument matches any category name containing that keyword, ignoring case; an empty category selects all discovered categories. `max_pages` is applied independently to each selected category listing. Product detail requests produce raw text values and metadata such as canonical URL and UTC scrape timestamp.

Pipeline order is important:

1. `CleaningPipeline` cleans the title; drops entries with missing titles or invalid prices; parses currency text to a float; maps star words (`One` through `Five`) to integers; extracts stock count; defaults invalid review counts to zero; title-cases the category; and removes raw intermediate fields.
2. `JsonWriterPipeline` opens the configured destination when the spider starts and appends each cleaned item as one JSON line.

The resulting records use this schema:

| Field | Type | Meaning |
| --- | --- | --- |
| `title` | string | Product title after whitespace cleanup |
| `price` | number | Parsed product price |
| `rating` | integer or null | Star rating from zero to five |
| `availability` | integer | Parsed available quantity, or zero when unavailable/unparseable |
| `reviews` | integer | Review count, defaulting to zero when unparseable |
| `category` | string | Product category |
| `url` | string | Product detail page URL |
| `scraped_at` | string | UTC ISO 8601 timestamp |

### Analytics Logic

`analytics.load_products(path)` reads each non-empty JSONL line into a DataFrame. It supplies required columns when missing, removes duplicate URLs, coerces numeric columns, fills missing review/availability counts with zero and missing titles/categories with defaults, and drops records whose price is not numeric. A missing or empty file produces an empty DataFrame.

`analytics.compute_kpis(df)` returns product count, mean/median/minimum/maximum price, average rating, average and total reviews, rating distribution, category counts, mean price by category, and the ten most common title keywords after basic tokenization and stopword removal. For empty data, it returns zero counts, null price/rating metrics, and empty distributions.

## HTTP API Reference

The API is rooted at `/api/v1` (except the health check).

| Method and path | Behavior |
| --- | --- |
| `GET /health` | Returns `{"status":"ok"}`. |
| `POST /api/v1/crawl` | Starts a crawl. Accepts `category` (default empty string) and `max_pages` (default 5). Returns `job_id`, `status`, and `output_file`. |
| `GET /api/v1/crawl/{job_id}/status` | Returns job status, output path, and optional error. Unknown IDs return 404. |
| `GET /api/v1/jobs` | Lists job IDs, status, category, and output path known by this API process. |
| `GET /api/v1/products?job_id={id}` | Returns cleaned records and their count. |
| `GET /api/v1/analytics?job_id={id}` | Returns the KPI object. |
| `GET /api/v1/download?job_id={id}` | Streams the cleaned records as CSV. |

The last three routes also accept `file=<path>` in place of `job_id`. The API docs UI is served at `/docs` by FastAPI.

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{"category":"travel","max_pages":3}'
```

Example response:

```json
{
  "job_id": "a1b2c3d4e5",
  "status": "running",
  "output_file": ".../data/raw/travel_a1b2c3d4e5.jsonl"
}
```

The actual job ID and absolute output path are generated at runtime.

## Local Development

Use Python 3.11 or newer. From the repository root, create a virtual environment and install `requirements.txt`.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the API and dashboard in separate terminals, both from the repository root:

```bash
uvicorn app.main:app --reload
```

```bash
streamlit run streamlit_app.py
```

The API listens on `http://localhost:8000` by default; Streamlit prints its local URL, normally `http://localhost:8501`. The dashboard reads the API base URL from `API_BASE_URL`, defaulting to `http://localhost:8000/api/v1`.

To run Scrapy independently of FastAPI and Streamlit:

```bash
python -m scrapy crawl products -a category=travel -a max_pages=3 -s OUTPUT_FILE=data/raw/travel.jsonl
```

Use `-a category=mystery` for another category. Omit the category argument to crawl all categories. The output path is relative to the project root in this example.

## Configuration and Boundaries

- Dependency versions and the Python minimum are declared in both `pyproject.toml` and `requirements.txt`; keep them aligned when changing dependencies.
- `API_BASE_URL` configures where Streamlit sends API requests.
- Scrapy's default output is `data/raw/products.jsonl`; API-triggered crawls set a unique output file with `OUTPUT_FILE`.
- The dashboard constrains its page slider to 1-10, but the API request model itself does not define that range.
- Scrapy obeys `robots.txt`, has a download delay, uses per-domain concurrency limits, and enables retries and AutoThrottle.
- CORS currently allows every origin. This is convenient for local development but should be restricted before deployment.
- Job state is in-memory, there is no database or durable queue, and no automated tests are included in the current repository.
- JSONL and generated output files can accumulate in `data/raw/`; decide on retention and cleanup before using the workflow for repeated or large crawls.