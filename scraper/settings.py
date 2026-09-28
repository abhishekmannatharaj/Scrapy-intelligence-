"""Scrapy settings: the single configuration hub for every connected system.

All values are read from environment variables (optionally loaded from a
project-root `.env` file), with safe local-dev defaults. Precedence, highest first:

    1. `scrapy crawl ... -s KEY=value`   (per-run override, used by the API layer)
    2. real environment variables         (CI, Docker, production)
    3. `.env` file                        (local development, never committed)
    4. defaults defined in this file

Every UPPERCASE name below is a Scrapy setting, so pipelines can read them with
`crawler.settings.get("POSTGRES_DSN")`. Other services (FastAPI, Celery) can also
`from scraper import settings` and share the exact same configuration.
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

try:  # python-dotenv is optional; without it, only real env vars are used
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


# --------------------------------------------------------------------------- #
# Env helpers
# --------------------------------------------------------------------------- #
def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}")


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be a number, got {raw!r}")


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list) -> list:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]


# --------------------------------------------------------------------------- #
# Environment profile (APP_ENV=dev|staging|prod)
# --------------------------------------------------------------------------- #
APP_ENV = env_str("APP_ENV", "dev").lower()

_PROFILES = {
    "dev": {"DOWNLOAD_DELAY": 0.5, "LOG_LEVEL": "INFO", "HTTPCACHE_ENABLED": True},
    "staging": {"DOWNLOAD_DELAY": 1.0, "LOG_LEVEL": "INFO", "HTTPCACHE_ENABLED": False},
    "prod": {"DOWNLOAD_DELAY": 1.0, "LOG_LEVEL": "WARNING", "HTTPCACHE_ENABLED": False},
}
if APP_ENV not in _PROFILES:
    raise ValueError(f"APP_ENV must be one of {sorted(_PROFILES)}, got {APP_ENV!r}")
_profile = _PROFILES[APP_ENV]


# --------------------------------------------------------------------------- #
# Scrapy core
# --------------------------------------------------------------------------- #
BOT_NAME = "scraper"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

ROBOTSTXT_OBEY = env_bool("ROBOTSTXT_OBEY", True)
USER_AGENT = env_str(
    "USER_AGENT",
    "competitor-intel-bot/1.0 (+https://example.com/bot-info; contact=intern@example.com)",
)

# Polite crawling
CONCURRENT_REQUESTS = env_int("CONCURRENT_REQUESTS", 8)
CONCURRENT_REQUESTS_PER_DOMAIN = env_int("CONCURRENT_REQUESTS_PER_DOMAIN", 4)
DOWNLOAD_DELAY = env_float("DOWNLOAD_DELAY", _profile["DOWNLOAD_DELAY"])

AUTOTHROTTLE_ENABLED = env_bool("AUTOTHROTTLE_ENABLED", True)
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = env_float("AUTOTHROTTLE_MAX_DELAY", 5.0)
AUTOTHROTTLE_TARGET_CONCURRENCY = env_float("AUTOTHROTTLE_TARGET_CONCURRENCY", 2.0)

RETRY_ENABLED = True
RETRY_TIMES = env_int("RETRY_TIMES", 2)

# Response cache: on in dev so repeated test crawls don't hammer the site.
# Cached prices can be stale, so it is off by default in staging/prod.
HTTPCACHE_ENABLED = env_bool("HTTPCACHE_ENABLED", _profile["HTTPCACHE_ENABLED"])
HTTPCACHE_EXPIRATION_SECS = env_int("HTTPCACHE_EXPIRATION_SECS", 3600)
HTTPCACHE_DIR = "httpcache"  # lives under .scrapy/ (already git-ignored)

LOG_LEVEL = env_str("LOG_LEVEL", _profile["LOG_LEVEL"]).upper()
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"


# --------------------------------------------------------------------------- #
# Crawl target (read by the spider's from_crawler)
# --------------------------------------------------------------------------- #
TARGET_START_URL = env_str("TARGET_START_URL", "https://books.toscrape.com/index.html")
TARGET_ALLOWED_DOMAINS = env_list("TARGET_ALLOWED_DOMAINS", ["books.toscrape.com"])


# --------------------------------------------------------------------------- #
# Storage backends
# --------------------------------------------------------------------------- #
# Comma-separated, e.g. STORAGE_BACKENDS=jsonl,postgres writes to both.
# Only "jsonl" is implemented today; "postgres" and "mongo" map to pipeline
# classes to be added in scraper/pipelines.py.
OUTPUT_FILE = env_str("OUTPUT_FILE", "data/raw/products.jsonl")
STORAGE_BACKENDS = [b.lower() for b in env_list("STORAGE_BACKENDS", ["jsonl"])]

_STORAGE_PIPELINES = {
    "jsonl": ("scraper.pipelines.JsonWriterPipeline", 800),
    "postgres": ("scraper.pipelines.PostgresPipeline", 810),
    "mongo": ("scraper.pipelines.MongoPipeline", 820),
}
_unknown = [b for b in STORAGE_BACKENDS if b not in _STORAGE_PIPELINES]
if _unknown:
    raise ValueError(
        f"Unknown STORAGE_BACKENDS {_unknown}; valid options: {sorted(_STORAGE_PIPELINES)}"
    )

ITEM_PIPELINES = {"scraper.pipelines.CleaningPipeline": 300}
for _backend in STORAGE_BACKENDS:
    _path, _priority = _STORAGE_PIPELINES[_backend]
    ITEM_PIPELINES[_path] = _priority


# --------------------------------------------------------------------------- #
# PostgreSQL
# --------------------------------------------------------------------------- #
POSTGRES_HOST = env_str("POSTGRES_HOST", "localhost")
POSTGRES_PORT = env_int("POSTGRES_PORT", 5432)
POSTGRES_DB = env_str("POSTGRES_DB", "competitor_intel")
POSTGRES_USER = env_str("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = env_str("POSTGRES_PASSWORD", "postgres")  # dev default only
POSTGRES_DSN = env_str(
    "POSTGRES_DSN",
    f"postgresql://{quote_plus(POSTGRES_USER)}:{quote_plus(POSTGRES_PASSWORD)}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)
POSTGRES_BATCH_SIZE = env_int("POSTGRES_BATCH_SIZE", 50)


# --------------------------------------------------------------------------- #
# MongoDB
# --------------------------------------------------------------------------- #
MONGO_URI = env_str("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = env_str("MONGO_DB", "competitor_intel")
MONGO_COLLECTION = env_str("MONGO_COLLECTION", "products")


# --------------------------------------------------------------------------- #
# Redis, RabbitMQ, Celery (distributed crawling)
# --------------------------------------------------------------------------- #
REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = env_str("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", RABBITMQ_URL)  # RabbitMQ = broker
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", REDIS_URL)  # Redis = results/state