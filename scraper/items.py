import scrapy


class ProductItem(scrapy.Item):
    """Raw fields as scraped; pipelines.py normalizes these into typed values."""

    title = scrapy.Field()
    price_raw = scrapy.Field()
    price = scrapy.Field()
    rating_raw = scrapy.Field()
    rating = scrapy.Field()
    availability_raw = scrapy.Field()
    availability = scrapy.Field()
    reviews_raw = scrapy.Field()
    reviews = scrapy.Field()
    category = scrapy.Field()
    url = scrapy.Field()
    scraped_at = scrapy.Field()
