"""Heuristic metadata spider: JSON-LD (Schema.org) > OpenGraph > XPath/CSS fallbacks.

Works on arbitrary storefronts. Extraction sources are merged field-by-field so a page with
partial structured data is completed from the next-best source.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import scrapy

from market_spider.items import ProductItem

CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR", "₹": "INR", "¥": "JPY"}
AVAILABILITY = {"instock": "In stock", "outofstock": "Out of stock", "soldout": "Out of stock",
                "preorder": "Pre-order", "backorder": "Backorder",
                "limitedavailability": "Limited availability", "discontinued": "Discontinued"}
RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
FIELDS = ("title", "price", "currency", "availability", "rating", "category",
          "image_url", "description")

PRODUCT_LINK_CSS = ", ".join([
    "article.product_pod h3 a", "a.title", ".product a", ".product-item a", ".product-card a",
    "a[itemprop=url]", 'a[href*="/product"]', 'a[href*="/item/"]', 'a[href*="/p/"]',
])
PAGINATION_CSS = ", ".join([
    "li.next a", "a[rel=next]", "link[rel=next]", "a.next", "a.next-page", ".pagination a.next",
])
PRODUCT_PAGE_MARKERS = ('.product_main, [itemtype*="schema.org/Product"], .product-detail, '
                        "#product, body.single-product, article.product_page")
_BAD_LINK = re.compile(r"add-to-cart|/cart|wishlist|login|account|checkout|javascript:|#", re.I)
_SPACES = re.compile(r"\s+")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _SPACES.sub(" ", str(value).replace("Â", "")).strip()
    return text or None


def parse_price(value: Any) -> tuple[float | None, str | None]:
    """'£51.77' -> (51.77, 'GBP'); '1.299,00 €' -> (1299.0, 'EUR')."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    text = str(value).replace("Â", "")
    cur = re.search(r"[£$€₹¥]|\b(?:USD|EUR|GBP|INR|JPY)\b", text)
    currency = CURRENCY_SYMBOLS.get(cur.group(0), cur.group(0)) if cur else None
    m = re.search(r"\d[\d.,]*", text)
    if not m:
        return None, currency
    num = m.group(0).rstrip(".,")
    if "," in num and "." in num:
        num = (num.replace(".", "").replace(",", ".") if num.rfind(",") > num.rfind(".")
               else num.replace(",", ""))
    elif "," in num:
        num = num.replace(",", ".") if re.search(r",\d{1,2}$", num) else num.replace(",", "")
    try:
        return float(num), currency
    except ValueError:
        return None, currency


def normalize_availability(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.rsplit("/", 1)[-1].replace(" ", "").replace("_", "").lower()
    return AVAILABILITY.get(key, text)


def _first(value: Any) -> Any:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url") or value.get("name")
    return value


def jsonld_products(response) -> list[dict]:
    found, stack = [], []
    for raw in response.xpath('//script[@type="application/ld+json"]/text()').getall():
        try:
            stack.append(json.loads(raw, strict=False))
        except ValueError:
            continue
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            types = node.get("@type")
            if "Product" in (types if isinstance(types, list) else [types]):
                found.append(node)
            if "@graph" in node:
                stack.append(node["@graph"])
    return found


def fields_from_jsonld(node: dict) -> dict[str, Any]:
    offers = _first(node.get("offers")) if isinstance(node.get("offers"), list) else node.get("offers")
    offers = offers if isinstance(offers, dict) else {}
    price, cur = parse_price(offers.get("price", offers.get("lowPrice")))
    rating = (node.get("aggregateRating") or {}).get("ratingValue")
    try:
        rating = float(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None
    category = _first(node.get("category"))
    return {"title": clean_text(node.get("name")), "price": price,
            "currency": offers.get("priceCurrency") or cur,
            "availability": normalize_availability(offers.get("availability")),
            "rating": rating, "category": clean_text(category) if isinstance(category, str) else None,
            "image_url": _first(node.get("image")), "description": clean_text(node.get("description"))}


def fields_from_opengraph(response) -> dict[str, Any]:
    def meta(*names):
        for n in names:
            v = response.xpath(f'//meta[@property="{n}" or @name="{n}"]/@content').get()
            if v:
                return v
    price, cur = parse_price(meta("product:price:amount", "og:price:amount"))
    return {"title": clean_text(meta("og:title")), "price": price,
            "currency": meta("product:price:currency", "og:price:currency") or cur,
            "availability": normalize_availability(meta("product:availability", "og:availability")),
            "category": clean_text(meta("product:category")),
            "image_url": meta("og:image"),
            "description": clean_text(meta("og:description", "description"))}


def fields_from_css(response) -> dict[str, Any]:
    def css(sel):
        return response.css(sel).get()

    raw_price = (css("[itemprop=price]::attr(content)") or css("p.price_color::text")
                 or css(".price ::text") or css(".product-price ::text")
                 or css(".woocommerce-Price-amount ::text") or css("[class*=price] ::text"))
    price, cur = parse_price(raw_price)
    star = css("p.star-rating::attr(class)") or ""
    rating = next((v for k, v in RATING_WORDS.items() if k in star.lower()), None)
    crumbs = response.css("ul.breadcrumb li a::text, nav[aria-label*=readcrumb] a::text, "
                          ".breadcrumbs a::text, .breadcrumb a::text").getall()
    image = (css(".item.active img::attr(src)") or css("#product_gallery img::attr(src)")
             or css(".product img::attr(src)") or css("img.img-responsive::attr(src)"))
    avail = " ".join(response.css("p.availability ::text, [itemprop=availability] ::text, "
                                  ".stock ::text, .availability ::text").getall())
    desc = css("#product_description + p::text") or css("[itemprop=description]::text") or \
        css("meta[name=description]::attr(content)")
    return {"title": clean_text(css("h1::text") or css("h1 ::text") or css("title::text")),
            "price": price, "currency": cur, "availability": normalize_availability(avail),
            "rating": rating, "category": clean_text(crumbs[-1]) if len(crumbs) >= 2 else None,
            "image_url": response.urljoin(image) if image else None,
            "description": clean_text(desc)}


def merge_sources(sources: list[tuple[str, dict]]) -> tuple[dict, str]:
    merged: dict[str, Any] = {}
    used: list[str] = []
    for name, data in sources:
        gained = False
        for f in FIELDS:
            if merged.get(f) in (None, "") and data.get(f) not in (None, ""):
                merged[f], gained = data[f], True
        if gained:
            used.append(name)
    return merged, "+".join(used)


class UniversalSpider(scrapy.Spider):
    name = "universal"

    def __init__(self, url: str | None = None, job_id: str | None = None,
                 max_pages: int | str = 50, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not url:
            raise ValueError("Pass the target with -a url=https://...")
        self.start_url = url
        self.job_id = job_id or str(uuid4())
        self.max_pages = int(max_pages)
        self.allowed_domains = [urlparse(url).hostname or ""]

    # --- request construction (overridden by DynamicSpider to add Playwright meta) ---
    def request_kwargs(self) -> dict:
        return {"meta": {"playwright": True, "playwright_include_page": True}}

    def make_request(self, url: str, **extra) -> scrapy.Request:
        request_kwargs = {**self.request_kwargs(), **extra}
        meta = request_kwargs.get("meta", {})
        callback = self.parse_with_page if meta.get("playwright_include_page") else self.parse
        return scrapy.Request(url, callback=callback, errback=self.on_error, **request_kwargs)

    async def start(self):
        yield self.make_request(self.start_url, dont_filter=True)

    async def on_error(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page is not None:
            await page.close()
        self.logger.warning("Request failed: %s", failure.request.url)

    # --- parsing ---
    async def parse_with_page(self, response):
        page = response.meta.get("playwright_page")
        try:
            for result in self.parse(response):
                yield result
        finally:
            if page is not None:
                await page.close()

    def parse(self, response):
        if not hasattr(response, "xpath"):
            return
        product_links = self.product_links(response)
        item = self.extract_product(response, len(product_links))
        if item is not None:
            yield item
        for link in product_links + self.pagination_links(response):
            yield self.make_request(link)

    def product_links(self, response) -> list[str]:
        hrefs = response.css(PRODUCT_LINK_CSS).xpath("@href").getall()
        links = {response.urljoin(h) for h in hrefs if h and not _BAD_LINK.search(h)}
        links.discard(response.url)
        return sorted(links)

    def pagination_links(self, response) -> list[str]:
        hrefs = response.css(PAGINATION_CSS).xpath("@href").getall()
        return sorted({response.urljoin(h) for h in hrefs if h})

    def extract_product(self, response, n_links: int = 0) -> ProductItem | None:
        ld_nodes = jsonld_products(response)
        is_product_page = bool(ld_nodes) or bool(response.css(PRODUCT_PAGE_MARKERS)) \
            or response.xpath('//meta[@property="og:type"]/@content').get() == "product"
        css_fields = fields_from_css(response)
        if not is_product_page:  # fallback: a page that links to <=1 products and has a price
            if not (n_links <= 1 and css_fields["price"] is not None and css_fields["title"]):
                return None
        sources = [("jsonld", fields_from_jsonld(ld_nodes[0]) if ld_nodes else {}),
                   ("og", fields_from_opengraph(response)), ("css", css_fields)]
        data, method = merge_sources(sources)
        if not data.get("title") or data.get("price") is None:
            return None
        if data.get("image_url"):
            data["image_url"] = response.urljoin(data["image_url"])
        return ProductItem(job_id=self.job_id, url=response.url,
                           source_domain=urlparse(response.url).hostname, extraction_method=method,
                           raw=ld_nodes[0] if ld_nodes else None, **data)
