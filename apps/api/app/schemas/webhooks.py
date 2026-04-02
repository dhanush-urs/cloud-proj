from pydantic import BaseModel


class WebhookProcessResponse(BaseModel):
    message: str
    event_type: str
    delivery_id: str | None = None
    repository_id: str | None = None
    refresh_job_id: str | None = None
    processed: bool = True
