"""MongoDB async connection pool (Motor). Stores raw/flexible product documents."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import get_settings

settings = get_settings()
_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_url, maxPoolSize=50, minPoolSize=2,
                                     serverSelectionTimeoutMS=5000)
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


def get_products_collection() -> AsyncIOMotorCollection:
    return get_mongo_db()[settings.mongo_products_collection]


async def ensure_indexes() -> None:
    col = get_products_collection()
    await col.create_index([("job_id", 1), ("url", 1)], unique=True)
    await col.create_index("source_domain")
    await col.create_index("price")


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
