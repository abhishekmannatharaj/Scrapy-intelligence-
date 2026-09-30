import scrapy


class ProductItem(scrapy.Item):
    job_id = scrapy.Field()
    url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    currency = scrapy.Field()
    availability = scrapy.Field()
    rating = scrapy.Field()
    category = scrapy.Field()
    image_url = scrapy.Field()
    description = scrapy.Field()
    source_domain = scrapy.Field()
    extraction_method = scrapy.Field()  # e.g. "jsonld+css"
    scraped_at = scrapy.Field()
    raw = scrapy.Field()  # raw JSON-LD node (stored in MongoDB only)
