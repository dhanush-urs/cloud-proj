from celery import Celery
import os
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
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


def dispatch_task(task, *args, **kwargs):
    """
    Dispatches a task. In dev mode (REPOBRAIN_SYNC_MODE=true), runs synchronously.
    Otherwise, enqueues in Celery.
    """
    sync_mode = os.getenv("REPOBRAIN_SYNC_MODE", "false").lower() == "true"
    
    if sync_mode:
        logger.info(f"Dev resilience: Executing task {task.name} synchronously.")
        return task.apply(args=args, kwargs=kwargs)
    
    logger.info(f"Enqueuing task {task.name} in Celery.")
    return task.delay(*args, **kwargs)