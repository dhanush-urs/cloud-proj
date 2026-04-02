import json

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.session import SessionLocal
from app.schemas.webhooks import WebhookProcessResponse
from app.services.incremental_refresh_service import IncrementalRefreshService
from app.services.repository_service import RepositoryService
from app.services.webhook_service import WebhookService

router = APIRouter(tags=["webhooks"])


def process_refresh_job_background(job_id: str):
    db = SessionLocal()
    try:
        refresh_service = IncrementalRefreshService(db)
        refresh_service.process_refresh_job(job_id)
    finally:
        db.close()


@router.post("/webhooks/github", response_model=WebhookProcessResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
):
    payload_bytes = await request.body()

    webhook_service = WebhookService(db)

    if not webhook_service.verify_github_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if webhook_service.is_duplicate_delivery(x_github_delivery):
        return WebhookProcessResponse(
            message="Duplicate delivery ignored",
            event_type=x_github_event or "unknown",
            delivery_id=x_github_delivery,
            processed=True,
        )

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = x_github_event or "unknown"

    if event_type == "ping":
        event = webhook_service.record_event(
            event_type=event_type,
            payload=payload,
            delivery_id=x_github_delivery,
            status="processed",
        )

        return WebhookProcessResponse(
            message="GitHub webhook ping received",
            event_type=event_type,
            delivery_id=event.delivery_id,
            processed=True,
        )

    event = webhook_service.record_event(
        event_type=event_type,
        payload=payload,
        delivery_id=x_github_delivery,
        status="received",
    )

    try:
        repository_url = webhook_service.extract_repository_url(payload)
        branch = webhook_service.extract_branch(event_type, payload)
        changed_files = webhook_service.extract_changed_files(event_type, payload)

        repository_service = RepositoryService(db)
        repository = repository_service.get_repository_by_url(repository_url)

        if not repository:
            webhook_service.update_event_status(
                event,
                status="ignored",
                error_message="Repository not registered in RepoBrain",
            )
            return WebhookProcessResponse(
                message="Repository not found in RepoBrain; webhook ignored",
                event_type=event_type,
                delivery_id=x_github_delivery,
                processed=True,
            )

        refresh_service = IncrementalRefreshService(db)
        refresh_job = refresh_service.create_refresh_job(
            repository=repository,
            event_type=event_type,
            branch=branch,
            changed_files=changed_files,
            trigger_source="webhook",
        )

        webhook_service.update_event_status(event, status="queued")

        background_tasks.add_task(process_refresh_job_background, refresh_job.id)

        return WebhookProcessResponse(
            message="Webhook accepted and refresh queued",
            event_type=event_type,
            delivery_id=x_github_delivery,
            repository_id=repository.id,
            refresh_job_id=refresh_job.id,
            processed=True,
        )

    except Exception as exc:
        webhook_service.update_event_status(
            event,
            status="failed",
            error_message=str(exc),
        )
        # Return 200 so GitHub does NOT retry. Record the failure in the event record.
        return WebhookProcessResponse(
            message=f"Webhook processing failed: {exc}",
            event_type=event_type,
            delivery_id=x_github_delivery,
            repository_id=None,
            refresh_job_id=None,
            processed=False,
        )
