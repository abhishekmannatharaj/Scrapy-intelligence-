BOT_NAME = "scraper"

SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

ROBOTSTXT_OBEY = True

USER_AGENT = (
    "competitor-intel-bot/1.0 "
    "(+https://example.com/bot-info; contact=intern@example.com)"
)

# Polite crawling defaults
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 0.5

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 5
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

RETRY_ENABLED = True
RETRY_TIMES = 2

ITEM_PIPELINES = {
    "scraper.pipelines.CleaningPipeline": 300,
    "scraper.pipelines.JsonWriterPipeline": 800,
}

# Default output location; the API layer overrides this per crawl job with -s OUTPUT_FILE=...
OUTPUT_FILE = "data/raw/products.jsonl"

LOG_LEVEL = "INFO"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
