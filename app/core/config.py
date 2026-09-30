"""Central configuration (12-factor, env-driven)."""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "market-pulse-crawler"
    environment: str = "development"
    cors_origins: list[str] = ["*"]

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "pulse"
    postgres_password: str = "pulse_change_me"
    postgres_db: str = "market_pulse"

    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_user: str = "pulse"
    mongo_password: str = "pulse_change_me"
    mongo_db: str = "market_pulse"
    mongo_products_collection: str = "products"

    redis_host: str = "localhost"
    redis_port: int = 6379

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "pulse"
    rabbitmq_password: str = "pulse_change_me"

    crawl_timeout_seconds: int = 3600
    dedup_ttl_seconds: int = 6 * 3600

    @property
    def _pg_auth(self) -> str:
        return f"{quote_plus(self.postgres_user)}:{quote_plus(self.postgres_password)}"

    @property
    def postgres_sync_url(self) -> str:
        return (f"postgresql+psycopg2://{self._pg_auth}@{self.postgres_host}:"
                f"{self.postgres_port}/{self.postgres_db}")

    @property
    def postgres_async_url(self) -> str:
        return (f"postgresql+asyncpg://{self._pg_auth}@{self.postgres_host}:"
                f"{self.postgres_port}/{self.postgres_db}")

    @property
    def mongo_url(self) -> str:
        auth = ""
        if self.mongo_user:
            auth = f"{quote_plus(self.mongo_user)}:{quote_plus(self.mongo_password)}@"
        suffix = "/?authSource=admin" if self.mongo_user else ""
        return f"mongodb://{auth}{self.mongo_host}:{self.mongo_port}{suffix}"

    @property
    def celery_broker_url(self) -> str:
        return (f"amqp://{quote_plus(self.rabbitmq_user)}:{quote_plus(self.rabbitmq_password)}"
                f"@{self.rabbitmq_host}:{self.rabbitmq_port}//")

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def redis_dedup_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
