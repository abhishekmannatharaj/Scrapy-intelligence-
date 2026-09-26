import json
import os
import re

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

RATING_WORDS = {"Zero": 0, "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class CleaningPipeline:
    """Normalizes raw scraped strings into typed, analysis-ready fields.

    - Strips currency symbols from price and casts to float
    - Maps star-rating word classes ("Three") to integers
    - Extracts stock count from free-text availability
    - Coerces review counts to int, defaulting to 0
    - Strips whitespace / HTML junk from titles
    """

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        title = (adapter.get("title") or "").strip()
        if not title:
            raise DropItem("Missing title")
        adapter["title"] = re.sub(r"\s+", " ", title)

        price_raw = adapter.get("price_raw") or ""
        price_clean = re.sub(r"[^\d.]", "", price_raw)
        try:
            adapter["price"] = round(float(price_clean), 2)
        except ValueError:
            raise DropItem(f"Unparseable price for '{title}': {price_raw!r}")

        adapter["rating"] = RATING_WORDS.get(adapter.get("rating_raw", ""), None)

        availability_raw = adapter.get("availability_raw") or ""
        match = re.search(r"(\d+)\s+available", availability_raw)
        adapter["availability"] = int(match.group(1)) if match else 0

        try:
            adapter["reviews"] = int(str(adapter.get("reviews_raw", "0")).strip())
        except ValueError:
            adapter["reviews"] = 0

        adapter["category"] = (adapter.get("category") or "Unknown").strip().title()

        for junk_field in ("price_raw", "rating_raw", "availability_raw", "reviews_raw"):
            adapter.pop(junk_field, None)

        return item


class JsonWriterPipeline:
    """Streams cleaned items to a JSONL file, one product per line.

    Output path is read from the OUTPUT_FILE setting so the API layer can
    point every crawl job at its own file.
    """

    def __init__(self, output_file: str):
        self.output_file = output_file
        self.file = None

    @classmethod
    def from_crawler(cls, crawler):
        output_file = crawler.settings.get("OUTPUT_FILE", "data/raw/products.jsonl")
        return cls(output_file)

    def open_spider(self, spider):
        directory = os.path.dirname(self.output_file) or "."
        os.makedirs(directory, exist_ok=True)
        self.file = open(self.output_file, "w", encoding="utf-8")

    def close_spider(self, spider):
        if self.file:
            self.file.close()

    def process_item(self, item, spider):
        line = json.dumps(dict(ItemAdapter(item)), ensure_ascii=False)
        self.file.write(line + "\n")
        return item
