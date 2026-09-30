"""Scrapy settings: politeness, Playwright handlers, and Mongo/Postgres/Redis pipelines."""
import sys
from pathlib import Path

# Make the shared `app` package (config, models) importable from the crawler.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT_NAME = "market_spider"
SPIDER_MODULES = ["market_spider.spiders"]
NEWSPIDER_MODULE = "market_spider.spiders"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
ROBOTSTXT_OBEY = False
DEFAULT_REQUEST_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}
LOG_LEVEL = "INFO"
FEED_EXPORT_ENCODING = "utf-8"

# Politeness / throughput
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.25
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 45
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Downloader middlewares: built-in retry tuned for flaky e-commerce sites.
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]
DOWNLOADER_MIDDLEWARES = {}

# Scrapy-Playwright: only requests with meta["playwright"]=True are rendered in a browser.
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "timeout": 30_000,
    "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 45_000
PLAYWRIGHT_MAX_CONTEXTS = 2
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 4


def should_abort_request(request) -> bool:
    """Skip heavy resources; metadata (og:image, JSON-LD) is in the HTML anyway."""
    return request.resource_type in {"image", "media", "font"}


PLAYWRIGHT_ABORT_REQUEST = should_abort_request

ITEM_PIPELINES = {
    "market_spider.pipelines.CleaningPipeline": 100,
    "market_spider.pipelines.RedisDedupPipeline": 200,
    "market_spider.pipelines.MongoPipeline": 300,
    "market_spider.pipelines.PostgresPipeline": 400,
}
