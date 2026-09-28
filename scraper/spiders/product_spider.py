from datetime import datetime, timezone

import scrapy

from scraper.items import ProductItem


class ProductSpider(scrapy.Spider):
    """Crawls books.toscrape.com as a stand-in e-commerce catalog.

    Selector strategy (hybrid):
      * CSS   -> simple class/tag lookups (links, title, price, rating, pagination)
      * XPath -> anything CSS cannot express: matching a table row by its label text,
                 picking a breadcrumb by position, collapsing messy whitespace

    Target site is configurable via settings / environment:
        TARGET_START_URL, TARGET_ALLOWED_DOMAINS

    Standalone run examples:
        scrapy crawl products -a category="travel" -a max_pages=2
        scrapy crawl products -a category="travel" -s OUTPUT_FILE=data/raw/travel.jsonl
        scrapy crawl products                       # crawls every category
    """

    name = "products"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/index.html"]

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        settings = crawler.settings
        spider.start_urls = [settings.get("TARGET_START_URL", cls.start_urls[0])]
        spider.allowed_domains = settings.getlist(
            "TARGET_ALLOWED_DOMAINS", cls.allowed_domains
        )
        return spider

    def __init__(self, category: str = "", max_pages: int = 5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_filter = (category or "").strip().lower()
        self.max_pages = int(max_pages)

    def parse(self, response):
        """Read the category sidebar and fan out to the matching category (or all)."""
        categories = {}
        for link in response.css("div.side_categories ul li ul li a"):
            name = (link.css("::text").get() or "").strip()
            href = link.attrib.get("href")
            if name and href:
                # response.urljoin -> always a complete URL with scheme + domain
                categories[name.lower()] = response.urljoin(href)

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
        """Extract product links from a category page and follow pagination."""
        category_name = response.meta.get("category_name", "Unknown")
        page_count = response.meta.get("page_count", 1)

        for href in response.css("article.product_pod h3 a::attr(href)").getall():
            yield scrapy.Request(
                response.urljoin(href),
                callback=self.parse_detail,
                meta={"category_name": category_name},
            )

        next_href = response.css("li.next a::attr(href)").get()
        if next_href and page_count < self.max_pages:
            yield scrapy.Request(
                response.urljoin(next_href),
                callback=self.parse_listing,
                meta={"category_name": category_name, "page_count": page_count + 1},
            )

    def parse_detail(self, response):
        item = ProductItem()

        item["title"] = (response.css("div.product_main h1::text").get() or "").strip()
   
        rating_classes = response.css("div.product_main p.star-rating::attr(class)").get("")
        item["rating_raw"] = rating_classes.replace("star-rating", "").strip()

        item["availability_raw"] = response.xpath(
            'normalize-space(//div[contains(@class, "product_main")]'
            '/p[contains(@class, "availability")])'
        ).get("")

        # Find the spec-table row by its label text, independent of row order.
        item["reviews_raw"] = response.xpath(
            '//table//tr[th[normalize-space(.)="Number of reviews"]]/td/text()'
        ).get("0")

        # Third breadcrumb item (Home > Books > <Category>) selected by position.
        breadcrumb_category = response.xpath(
            '//ul[@class="breadcrumb"]/li[3]/a/text()'
        ).get()
        item["category"] = (
            breadcrumb_category.strip()
            if breadcrumb_category
            else response.meta.get("category_name", "Unknown")
        )

        item["url"] = response.url  # absolute: scheme + domain + path
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        yield item