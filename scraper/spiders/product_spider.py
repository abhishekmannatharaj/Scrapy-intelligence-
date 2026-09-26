from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from scraper.items import ProductItem


class ProductSpider(scrapy.Spider):
    """Crawls books.toscrape.com as a stand-in e-commerce catalog.

    Standalone run examples:
        scrapy crawl products -a category="travel" -s OUTPUT_FILE=data/raw/travel.jsonl
        scrapy crawl products                       # crawls every category
    """

    name = "products"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/index.html"]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def __init__(self, category: str = "", max_pages: int = 5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_filter = (category or "").strip().lower()
        self.max_pages = int(max_pages)

    def parse(self, response):
        """Read the category sidebar and fan out to the matching category (or all)."""
        category_links = response.css("div.side_categories ul li ul li a")
        categories = {}
        for link in category_links:
            name = (link.css("::text").get() or "").strip()
            href = link.attrib.get("href")
            if name and href:
                categories[name.lower()] = urljoin(response.url, href)

        if self.category_filter:
            matches = {
                name: url
                for name, url in categories.items()
                if self.category_filter in name
            }
            if not matches:
                self.logger.warning(
                    "No category matched '%s'. Available: %s",
                    self.category_filter,
                    ", ".join(sorted(categories)),
                )
                return
        else:
            matches = categories

        for name, url in matches.items():
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={"category_name": name.title(), "page_count": 1},
            )

    def parse_listing(self, response):
        """Extract product cards from a category page and follow pagination."""
        category_name = response.meta.get("category_name", "Unknown")
        page_count = response.meta.get("page_count", 1)

        for card in response.css("article.product_pod"):
            relative_url = card.css("h3 a::attr(href)").get()
            if not relative_url:
                continue
            detail_url = urljoin(response.url, relative_url)
            yield scrapy.Request(
                detail_url,
                callback=self.parse_detail,
                meta={"category_name": category_name},
            )

        next_href = response.css("li.next a::attr(href)").get()
        if next_href and page_count < self.max_pages:
            next_url = urljoin(response.url, next_href)
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing,
                meta={"category_name": category_name, "page_count": page_count + 1},
            )

    def parse_detail(self, response):
        item = ProductItem()
        item["title"] = (response.css("div.product_main h1::text").get() or "").strip()
        item["price_raw"] = response.css("p.price_color::text").get("")
        item["availability_raw"] = " ".join(
            response.css("p.availability::text").getall()
        ).strip()

        rating_classes = response.css("p.star-rating::attr(class)").get("") or ""
        item["rating_raw"] = rating_classes.replace("star-rating", "").strip()

        reviews_raw = response.xpath(
            "//table//tr[th[contains(text(),'Number of reviews')]]/td/text()"
        ).get("0")
        item["reviews_raw"] = reviews_raw

        breadcrumb_category = response.css("ul.breadcrumb li:nth-child(3) a::text").get()
        item["category"] = (
            breadcrumb_category.strip()
            if breadcrumb_category
            else response.meta.get("category_name", "Unknown")
        )
        item["url"] = response.url
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        yield item
