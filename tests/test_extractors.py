from market_spider.spiders.dynamic_spider import DynamicSpider
from market_spider.spiders.universal_spider import UniversalSpider, parse_price
from scrapy.http import HtmlResponse

BOOK = """<html><body><ul class="breadcrumb"><li><a>Home</a></li><li><a>Books</a></li>
<li><a>Poetry</a></li><li class="active">A Light in the Attic</li></ul>
<article class="product_page"><div class="product_main"><h1>A Light in the Attic</h1>
<p class="price_color">Â£51.77</p><p class="instock availability"> In stock (22 available) </p>
<p class="star-rating Three"></p></div></article></body></html>"""

JSONLD = """<html><head><script type="application/ld+json">{"@type":"Product","name":"Desk Lamp",
"image":["/l.jpg"],"offers":{"@type":"Offer","price":"1,299.50","priceCurrency":"INR",
"availability":"https://schema.org/InStock"},"aggregateRating":{"ratingValue":"4.5"}}
</script></head><body><h1>x</h1></body></html>"""

LISTING = """<html><body><h1>Poetry</h1><article class="product_pod"><h3><a href="a_1/index.html">A</a></h3>
<p class="price_color">£1.00</p></article><article class="product_pod"><h3><a href="b_2/index.html">B</a></h3>
<p class="price_color">£2.00</p></article><li class="next"><a href="page-2.html">next</a></li></body></html>"""


def _resp(url, body):
    return HtmlResponse(url, body=body.encode(), encoding="utf-8")


def test_parse_price_variants():
    assert parse_price("£51.77") == (51.77, "GBP")
    assert parse_price("1.299,00 €") == (1299.0, "EUR")
    assert parse_price("$1,299.00") == (1299.0, "USD")
    assert parse_price("n/a") == (None, None)


def test_css_fallback_on_books_detail_page():
    spider = UniversalSpider(url="https://books.toscrape.com/", job_id="j1")
    items = list(spider.parse(_resp("https://books.toscrape.com/catalogue/x/index.html", BOOK)))
    item = items[0]
    assert item["price"] == 51.77 and item["currency"] == "GBP"
    assert item["category"] == "Poetry" and item["rating"] == 3
    assert item["availability"].startswith("In stock")


def test_jsonld_takes_priority():
    spider = UniversalSpider(url="https://shop.test/", job_id="j1")
    item = next(iter(spider.parse(_resp("https://shop.test/p/lamp", JSONLD))))
    assert item["title"] == "Desk Lamp" and item["price"] == 1299.5
    assert item["availability"] == "In stock" and item["rating"] == 4.5
    assert item["extraction_method"].startswith("jsonld")


def test_listing_page_yields_links_not_items():
    spider = UniversalSpider(url="https://books.toscrape.com/", job_id="j1")
    out = list(spider.parse(_resp("https://books.toscrape.com/catalogue/page-1.html", LISTING)))
    urls = {r.url for r in out}
    assert all(not hasattr(o, "fields") for o in out)
    assert "https://books.toscrape.com/catalogue/a_1/index.html" in urls
    assert "https://books.toscrape.com/catalogue/page-2.html" in urls


def test_universal_requests_use_playwright_with_page_cleanup_callback():
    spider = UniversalSpider(url="https://books.toscrape.com/", job_id="j1")
    request = spider.make_request(spider.start_url)

    assert request.meta["playwright"] is True
    assert request.meta["playwright_include_page"] is True
    assert request.callback == spider.parse_with_page


def test_dynamic_requests_keep_their_existing_page_policy():
    spider = DynamicSpider(url="https://shop.test/", job_id="j1")
    request = spider.make_request(spider.start_url)

    assert request.meta["playwright"] is True
    assert request.meta["playwright_include_page"] is False
    assert request.meta["playwright_page_methods"]
