# E-Commerce Competitor Intelligence Dashboard

A small data collection and analysis application built with Scrapy, FastAPI, Pandas, and Streamlit. It crawls the sample catalog at [Books to Scrape](https://books.toscrape.com/), normalizes product details into JSON Lines files, calculates summary metrics, and presents the results in an interactive dashboard.

> Books to Scrape is a demonstration site. This project is an example workflow, built for practice.

<img width="1500" height="645" alt="image" src="https://github.com/user-attachments/assets/441a9d91-ff07-4aa9-be6f-d1c38092b845" />

<img width="727" height="320" alt="image" src="https://github.com/user-attachments/assets/a53fb3a0-1733-419a-8a6c-42cde1a389ad" />

<img width="1869" height="908" alt="image" src="https://github.com/user-attachments/assets/d053a032-a3eb-4eff-92da-aa99878bb498" />



## Features

- Crawl one matching book category or all categories, with a configurable page limit.
- Track background crawl jobs through the API.
- Store each crawl as a separate JSONL file under `data/raw/`.
- Clean and analyze product data: price, rating, availability, reviews, categories, and title keywords.
- View KPIs, charts, and a price-filtered product catalog in Streamlit.
- Download filtered dashboard data or an API-generated CSV.

## Project Structure

```text
.
├── app/                  # FastAPI application, API routes, and analytics
├── data/raw/             # Sample crawl output and generated JSONL files
├── scraper/              # Scrapy settings, spider, items, and pipelines
├── streamlit_app.py      # Streamlit dashboard
├── scrapy.cfg            # Scrapy project settings entry point
├── pyproject.toml        # Project metadata and pinned dependencies
└── requirements.txt      # pip-compatible dependency list
```

For the complete file-by-file guide and data flow, see [about.md](about.md).

## Requirements

- Python 3.11 or newer
- Internet access for the sample crawl

## Setup

From the repository root, create and activate a virtual environment, then install dependencies.

PowerShell:

```powershell
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in that terminal, then activate the environment again.


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

Omit `-a category=travel` to crawl every category. The output path can be changed with `OUTPUT_FILE`.

## Output Data

Each non-empty JSONL line represents one product. The normalized fields are `title`, `price`, `rating`, `availability`, `reviews`, `category`, `url`, and `scraped_at`. Numeric fields are stored as numbers, and timestamps use UTC ISO 8601 format. Example:

```json
{"title":"A Sample Book","category":"Travel","url":"https://books.toscrape.com/catalogue/sample/index.html","scraped_at":"2026-09-26T20:27:07+00:00","price":26.08,"rating":5,"availability":1,"reviews":0}
```

## Operational Notes

- Crawl job metadata is stored in memory. Restarting the API loses job status lookup, although JSONL files remain on disk.
- The API enables permissive CORS and is intended for local demonstration; review this before exposing it publicly.
- Scrapy obeys `robots.txt` and uses download delays, retries, and AutoThrottle settings.
- A category is matched as a case-insensitive substring of the site's category names. A keyword with no match produces an empty crawl.
- No automated test suite is currently included in the repository.
