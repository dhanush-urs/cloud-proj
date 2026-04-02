from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "repobrain_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=(
        "app.workers.tasks_ingest",
        "app.workers.tasks_parse",
        "app.workers.tasks_graph",
        "app.workers.tasks_embed",
    ),
)