"""SQLAlchemy engines/sessions: async for the API, sync for Celery and Scrapy pipelines."""
from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


async_engine = create_async_engine(settings.postgres_async_url, pool_pre_ping=True, pool_size=10)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

sync_engine = create_engine(settings.postgres_sync_url, pool_pre_ping=True, pool_size=5)
SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.db import models  # noqa: F401  (register tables)

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
