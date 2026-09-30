"""Celery app: RabbitMQ as broker, Redis as result backend."""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "market_pulse",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.crawl_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_queue="crawl",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
)
