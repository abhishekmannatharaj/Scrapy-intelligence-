"""Scrapy-Playwright spider: renders JavaScript (lazy lists, infinite scroll) before parsing."""
from scrapy_playwright.page import PageMethod

from market_spider.spiders.universal_spider import UniversalSpider

SCROLL_JS = """
async () => {
  let last = 0;
  for (let i = 0; i < 15; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 400));
    if (document.body.scrollHeight === last) break;
    last = document.body.scrollHeight;
  }
}
"""


class DynamicSpider(UniversalSpider):
    name = "dynamic"

    def request_kwargs(self) -> dict:
        return {"meta": {
            "playwright": True,
            "playwright_include_page": False,
            "playwright_page_methods": [
                PageMethod("wait_for_load_state", "networkidle"),
                PageMethod("evaluate", SCROLL_JS),
                PageMethod("wait_for_timeout", 300),
            ],
        }}
