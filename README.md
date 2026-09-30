# market-pulse-crawler

Distributed e-commerce crawling and market-intelligence platform.

```
Streamlit ──► FastAPI ──► RabbitMQ ──► Celery worker ──► Scrapy (+Playwright)
                │                            │                  │
                ├── PostgreSQL ◄─────────────┴── job status     ├─► MongoDB (raw docs)
                └── MongoDB                                     ├─► PostgreSQL (structured)
                         Redis: Celery results + item dedup ◄───┘
```
# 🚀 Scalable E-Commerce Scraper Platform

A production-grade, distributed web crawling architecture built to scrape dynamic, JavaScript-heavy e-commerce websites at scale.

## 📌 Architecture Overview (The 30-Second Mental Model)

Think of this platform as an **Airport Baggage System**:

```text
[User on Streamlit UI] ──(1) Clicks "Start Crawl"──► [FastAPI API]
                                                           │
                                             (2) Pushes task ticket (JSON)
                                                           ▼
                                                    [RabbitMQ Broker]
                                                           │
                                             (3) Pulls task when free
                                                           ▼
                                                    [Celery Worker]
                                                           │
                                      (4) Launches Scrapy + Playwright
                                                           ▼
                                             Extracts Product Data
                                                    /         \
                             (5) Raw Catalog Docs  /           \ (6) Job Status & Audit
                                                  ▼             ▼
                                            [MongoDB]     [PostgreSQL]
                                                  \             /
                                                   ▼           ▼
                                      [Streamlit Analytics Dashboard]
                                      (Aggregates KPIs with Pandas)
```

---

## 🏗️ System Components

The infrastructure is fully decoupled into specialized services, ensuring the API remains highly responsive while workers handle heavy compute loads:

*   **Front-End / UI (`Streamlit`)**  
    *   *Path:* `dashboard/app.py`
    *   *Role:* The control center where users input target URLs, configure crawler limits (e.g., max pages), and trigger jobs. It also acts as the real-time analytics dashboard aggregating KPIs using **Pandas**.
*   **API Gateway (`FastAPI`)**  
    *   *Path:* `app/api/v1/endpoints/jobs.py`
    *   *Role:* Receives inbound HTTP requests. To prevent connection timeouts or UI freezing, it instantly generates a unique `job_id`, logs the initial state in PostgreSQL, and passes the execution ticket to RabbitMQ within **5 milliseconds**.
*   **Message Broker (`RabbitMQ`)**  
    *   *Role:* A robust message queue that securely holds tasks in memory, enabling load balancing and task throttling before distributing workloads to background instances.
*   **Distributed Task Queue (`Celery Worker`)**  
    *   *Path:* `app/tasks/crawl_tasks.py`
    *   *Role:* Asynchronous background processes that poll RabbitMQ. When a worker picks up a task, it spawns **Scrapy** in an isolated runtime environment and spins up **Playwright (Chromium)** to render complex, JavaScript-driven e-commerce layers. Data is cleanly extracted via JSON-LD, OpenGraph tags, and fallback CSS selectors.
*   **Document Store (`MongoDB`)**  
    *   *Role:* A flexible, schemaless NoSQL database acting as the primary data sink for raw e-commerce product catalogs and unstructured JSON-LD payloads.
*   **Relational Database (`PostgreSQL`)**  
    *   *Role:* The system's source of truth for transactional states. It tracks granular job lifecycles (`PENDING` → `RUNNING` → `SUCCESS`), timestamps, and crawl metadata for auditing.
*   **Caching & Coordination (`Redis`)**  
    *   *Role:* A low-latency, in-memory data store leveraged by Celery to update real-time execution states and maintain global de-duplication arrays for crawled URLs.

# 🚀 Quickstart & Operations Guide

### 1. Prerequisites & Environment Setup
*   **Docker Desktop**: Ensure Docker Desktop is installed and the engine status is green.
*   **Python Tooling**: Built using Python 3.12+ managed via `uv`.

```powershell
# 1. Initialize and activate virtual environment
uv venv
.venv\Scripts\activate

# 2. Install dependencies locally (for testing/linting)
uv pip install -e .
uv pip install pytest
```

### 2. Booting the Complete Infrastructure
All 7 services (FastAPI, Celery Worker, MongoDB, PostgreSQL, Redis, RabbitMQ, and Streamlit) are orchestrated via Docker Compose:

```powershell
# Copy environment variables template
Copy-Item .env.example .env

# Launch the complete cluster in the background
docker compose up -d

# Verify all services are healthy and running
docker compose ps
```

### 3. Service Access Points

| Service | Port / URL | Default Credentials | Description |
| :--- | :--- | :--- | :--- |
| **Streamlit UI** | http://localhost:8501 | — | Interactive crawl trigger & analytics dashboard |
| **FastAPI Swagger Docs** | http://localhost:8000/docs | — | REST endpoints for job dispatching & querying |
| **RabbitMQ Console** | http://localhost:15672 | `guest` / `guest` | AMQP task queue monitoring & throughput charts |
| **MongoDB** | `localhost:27017` | — | Document store for raw product records & JSON-LD |
| **PostgreSQL** | `localhost:5432` | User: `postgres`, DB: `postgres` | Relational audit log for crawl jobs and status |
| **Redis** | `localhost:6379` | — | Task state caching & URL deduplication |

### 4. Running a Crawl Job
1. Open the Streamlit Dashboard at http://localhost:8501.
2. Navigate to **Trigger Crawl** in the sidebar.
3. Enter a target URL (e.g., `https://books.toscrape.com/catalogue/category/books_1/index.html`) and set **Max pages** (e.g., `2`).
4. Click **Start Crawl**.
5. Monitor task progression (`PENDING` → `RUNNING` → `SUCCESS`).
6. Navigate to **Market Analytics** to inspect KPI aggregations, price distribution histograms, and download CSV exports.

### 5. Day-to-Day Development & Useful Commands

#### Run Unit Tests Locally
```powershell
\$env:PYTHONPATH=".;crawler;app"
pytest -v
```

#### Fast Service Restarts (No Rebuild Needed for Python Code Edits)
```powershell
# Restart Celery worker after updating Scrapy settings/spiders
docker compose restart worker

# Restart API server after route updates
docker compose restart api

# Restart Streamlit dashboard
docker compose restart dashboard
```

#### Inspect Live Container Logs
```powershell
# Stream logs for background crawler tasks
docker compose logs -f worker

# Stream logs for API requests
docker compose logs -f api
```

#### Shut Down Stack
```powershell
# Stop services while preserving database volumes
docker compose down

# Stop and wipe all database volumes (Factory Reset)
docker compose down -v
```

## How it works

- **Jobs**: `POST /jobs` stores a `CrawlJob` (PostgreSQL), enqueues `crawl.run` on RabbitMQ
  (task id = job id) and returns `202`. Status moves `pending → running → success | failed`.
- **Worker**: each job runs `CrawlerProcess` in a fresh interpreter (`python -m app.tasks.crawl_tasks`),
  because Twisted's reactor can't be restarted in a long-lived worker. A timeout guards runaway crawls.
- **Extraction** (`universal_spider.py`): JSON-LD Product → OpenGraph → CSS/XPath fallbacks, merged
  per field; `extraction_method` records which sources contributed. Pages are classified as
  product vs listing to avoid emitting listing pages as products. Follows product links and pagination
  on the same domain only.
- **JS sites**: `spider: "dynamic"` renders via Playwright (waits for network idle, scrolls for lazy
  lists; images/fonts/media are blocked for speed). Only the worker image ships Chromium.
- **Pipelines**: clean → Redis dedup (per job+URL, TTL) → MongoDB bulk upsert (incl. raw JSON-LD)
  → PostgreSQL batched upsert (`ON CONFLICT (job_id, url)`).
- **Analytics** (`app/services/analytics.py`): KPIs, price distribution, catalog mix, competitor
  comparison with a price index. Used by `/products/analytics` and the dashboard.

`max_pages` is the number of pages fetched (listing + detail pages), not products.


## Notes

- `robots.txt` is obeyed by default (`ROBOTSTXT_OBEY`); set a real contact in `USER_AGENT`.
  Only crawl sites whose terms permit it.
- Tables are created at API startup (`create_all`); add Alembic before schema changes in production.
- `Dockerfile` is an addition to the requested tree (compose needs an image): `base` for
  api/dashboard, `worker` adds Chromium.
