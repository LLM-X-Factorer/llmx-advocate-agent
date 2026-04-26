from celery import Celery

from llmx_advocate.settings import get_settings

settings = get_settings()

app = Celery(
    "llmx_advocate",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["llmx_advocate.worker.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
