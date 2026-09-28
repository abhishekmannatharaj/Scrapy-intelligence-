# E-Commerce Competitor Intelligence Dashboard

A small data collection and analysis application built with Scrapy, FastAPI, Pandas, and Streamlit. It crawls the sample catalog at [Books to Scrape](https://books.toscrape.com/), normalizes product details into JSON Lines files, calculates summary metrics, and presents the results in an interactive dashboard.

> Books to Scrape is a demonstration site. This project is an example workflow, built for practice.

<img width="1500" height="645" alt="image" src="https://github.com/user-attachments/assets/441a9d91-ff07-4aa9-be6f-d1c38092b845" />

<img width="727" height="320" alt="image" src="https://github.com/user-attachments/assets/a53fb3a0-1733-419a-8a6c-42cde1a389ad" />

<img width="1869" height="908" alt="image" src="https://github.com/user-attachments/assets/d053a032-a3eb-4eff-92da-aa99878bb498" />



## Features

- Crawl a specific category or all categories with a configurable page limit.
- Launch background jobs through FastAPI and track status by job ID.
- Store each crawl as a separate JSONL file in `data/raw/`.
- Clean and normalize product data for price, rating, availability, reviews, category, and metadata.
- View summary KPIs, charts, and a price-filtered catalog in Streamlit.
- Download filtered results or API-generated CSV exports.
- Use environment-driven Scrapy settings for target URLs, concurrency, caching, storage backends, and deployment profiles.

## Project Structure

```text
.
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
│       └── *.jsonl
├── scraper/
│   ├── __init__.py
│   ├── items.py
│   ├── pipelines.py
│   ├── settings.py
│   └── spiders/
│       ├── __init__.py
│       └── product_spider.py
├── about.md
├── streamlit_app.py
├── scrapy.cfg
├── pyproject.toml
├── requirements.txt
└── README.md
```

For the complete project guide and data flow, see [about.md](about.md).

## Requirements

- Python 3.11 or newer
- Internet access for the sample crawl

## Environment Configuration

The scraper is configured through [scraper/settings.py](scraper/settings.py). It supports:

- environment variables and optional `.env` loading
- `APP_ENV` profiles: `dev`, `staging`, and `prod`
- target configuration via `TARGET_START_URL` and `TARGET_ALLOWED_DOMAINS`
- polite crawl settings like `DOWNLOAD_DELAY`, `CONCURRENT_REQUESTS`, and `AUTOTHROTTLE_*`
- optional storage backends via `STORAGE_BACKENDS` (`jsonl`, `postgres`, `mongo`)
- output file override with `OUTPUT_FILE`

Example `.env` values:

```env
APP_ENV=dev
TARGET_START_URL=https://books.toscrape.com/index.html
TARGET_ALLOWED_DOMAINS=books.toscrape.com
OUTPUT_FILE=data/raw/travel.jsonl
ROBOTSTXT_OBEY=true
CONCURRENT_REQUESTS=8
```

## Setup

From the repository root, create and activate a virtual environment, then install dependencies.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

then activate the environment again.

## Run the Application

Start the API in one terminal:

```bash
uvicorn app.main:app --reload
```

Start the dashboard in a second terminal, using the same activated environment:

```bash
streamlit run streamlit_app.py
```

Open the Streamlit URL printed by the command (normally `http://localhost:8501`). The API health check is at `http://localhost:8000/health`; interactive API documentation is at `http://localhost:8000/docs`.

The dashboard defaults to the `travel` category. Enter a category keyword and choose a page limit, then run the crawl. An empty category in the API means all categories.

## API

All versioned routes are prefixed with `/api/v1`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/crawl` | Start a crawl. JSON body: `{"category":"travel","max_pages":3}`. |
| `GET` | `/api/v1/crawl/{job_id}/status` | Get a crawl's status and output path. |
| `GET` | `/api/v1/jobs` | List jobs tracked by this API process. |
| `GET` | `/api/v1/products?job_id={id}` | Return cleaned products for a job. |
| `GET` | `/api/v1/analytics?job_id={id}` | Return KPIs and distributions for a job. |
| `GET` | `/api/v1/download?job_id={id}` | Download a job's products as CSV. |

The products, analytics, and download routes also accept a `file` query parameter for an existing JSONL path instead of `job_id`.

## Run a Crawl Without the API

With dependencies installed, Scrapy can be run directly from the repository root:

```bash
python -m scrapy crawl products -a category=travel -a max_pages=3 -s OUTPUT_FILE=data/raw/travel.jsonl
```

Use `-a category=mystery` for another category. Omit the category argument to crawl every category. The output path can be changed with `OUTPUT_FILE`.

## Output Data

Each non-empty JSONL line represents one product. The normalized fields are `title`, `price`, `rating`, `availability`, `reviews`, `category`, `url`, and `scraped_at`.

Example:

```json
{"title":"A Sample Book","category":"Travel","url":"https://books.toscrape.com/catalogue/sample/index.html","scraped_at":"2026-09-26T20:27:07+00:00","price":26.08,"rating":5,"availability":1,"reviews":0}
```

## Scraper Behavior

The crawler in [scraper/spiders/product_spider.py](scraper/spiders/product_spider.py) reads category names from the side menu, matches a category filter as a case-insensitive substring when supplied, and walks pagination up to the configured `max_pages` value. It also resolves the start URL and allowed domains from Scrapy settings at startup via `from_crawler`.

The spider uses a hybrid selector strategy:

- CSS selectors for simple class and attribute lookups
- XPath for table-row and breadcrumb lookups that require positional or label-based matching

## Operational Notes

- Crawl job metadata is stored in memory. Restarting the API loses job status lookup, although JSONL outputs remain on disk.
- The API enables permissive CORS and is intended for local demonstration; review this before exposing it publicly.
- Scrapy obeys `robots.txt` and uses download delays, retries, and AutoThrottle settings.
- A category match is case-insensitive and uses substring matching against the site’s category names. A keyword with no match produces an empty crawl.
- No automated test suite is currently included in the repository.