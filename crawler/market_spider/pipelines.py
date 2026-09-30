"""Item pipelines: clean -> dedupe (Redis) -> MongoDB -> PostgreSQL."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import redis
from itemadapter import ItemAdapter
from pymongo import MongoClient, UpdateOne
from scrapy.exceptions import DropItem
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.models import CrawlJob, ProductRecord
from app.db.postgres import Base, SyncSessionLocal, sync_engine

PG_COLUMNS = ["job_id", "url", "title", "price", "currency", "availability", "rating",
              "category", "image_url", "description", "source_domain", "extraction_method",
              "scraped_at"]
_WS = re.compile(r"\s+")


class CleaningPipeline:
    def process_item(self, item, spider):
        data = ItemAdapter(item)
        for key in ("title", "availability", "category", "description", "currency"):
            if isinstance(data.get(key), str):
                data[key] = _WS.sub(" ", data[key]).strip() or None
        if not data.get("title"):
            raise DropItem(f"Missing title: {data.get('url')}")
        if isinstance(data.get("description"), str):
            data["description"] = data["description"][:5000]
        data["scraped_at"] = datetime.now(timezone.utc)
        return item


class RedisDedupPipeline:
    """Cross-process dedup keyed by (job, url); the TTL bounds key growth."""

    def __init__(self):
        s = get_settings()
        self.client = redis.Redis.from_url(s.redis_dedup_url)
        self.ttl = s.dedup_ttl_seconds

    def process_item(self, item, spider):
        data = ItemAdapter(item)
        digest = hashlib.sha1(data["url"].encode()).hexdigest()
        if not self.client.set(f"dedup:{data['job_id']}:{digest}", 1, nx=True, ex=self.ttl):
            raise DropItem(f"Duplicate: {data['url']}")
        return item

    def close_spider(self, spider):
        self.client.close()


class MongoPipeline:
    BATCH = 50

    def open_spider(self, spider):
        s = get_settings()
        self.client = MongoClient(s.mongo_url)
        self.col = self.client[s.mongo_db][s.mongo_products_collection]
        self.col.create_index([("job_id", 1), ("url", 1)], unique=True)
        self.ops: list[UpdateOne] = []

    def process_item(self, item, spider):
        doc = ItemAdapter(item).asdict()
        self.ops.append(UpdateOne({"job_id": doc["job_id"], "url": doc["url"]},
                                  {"$set": doc}, upsert=True))
        if len(self.ops) >= self.BATCH:
            self._flush()
        return item

    def _flush(self):
        if self.ops:
            self.col.bulk_write(self.ops, ordered=False)
            self.ops = []

    def close_spider(self, spider):
        self._flush()
        self.client.close()


class PostgresPipeline:
    BATCH = 50

    def open_spider(self, spider):
        Base.metadata.create_all(sync_engine)
        with SyncSessionLocal() as s:  # the FK target must exist (also for manual runs)
            if s.get(CrawlJob, spider.job_id) is None:
                s.add(CrawlJob(id=spider.job_id, url=spider.start_url, spider=spider.name,
                               max_pages=spider.max_pages, status="running"))
                s.commit()
        self.buffer: list[dict] = []

    def process_item(self, item, spider):
        data = ItemAdapter(item)
        self.buffer.append({c: data.get(c) for c in PG_COLUMNS})
        if len(self.buffer) >= self.BATCH:
            self._flush()
        return item

    def _flush(self):
        if not self.buffer:
            return
        stmt = insert(ProductRecord).values(self.buffer)
        update = {c: stmt.excluded[c] for c in PG_COLUMNS if c not in ("job_id", "url")}
        stmt = stmt.on_conflict_do_update(constraint="uq_product_job_url", set_=update)
        with SyncSessionLocal() as s:
            s.execute(stmt)
            s.commit()
        self.buffer = []

    def close_spider(self, spider):
        self._flush()
