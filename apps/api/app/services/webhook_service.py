import hashlib
import hmac
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.webhook_event import WebhookEvent
from app.services.github_api_service import GitHubAPIService

settings = get_settings()


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.github_api_service = GitHubAPIService()

    def verify_github_signature(self, payload_bytes: bytes, signature_header: str | None) -> bool:
        secret = settings.GITHUB_WEBHOOK_SECRET

        if not secret:
            # Dev fallback only.
            return True

        if not signature_header:
            return False

        if not signature_header.startswith("sha256="):
            return False

        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature_header)

    def is_duplicate_delivery(self, delivery_id: str | None) -> bool:
        if not delivery_id:
            return False

        existing = self.db.scalar(
            select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
        )
        return existing is not None

    def record_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        delivery_id: str | None = None,
        status: str = "received",
        error_message: str | None = None,
    ) -> WebhookEvent:
        repository_url = self.extract_repository_url(payload)
        branch = self.extract_branch(event_type, payload)
        action = payload.get("action")

        event = WebhookEvent(
            provider="github",
            event_type=event_type,
            delivery_id=delivery_id,
            repository_url=repository_url,
            branch=branch,
            action=action,
            status=status,
            payload_json=json.dumps(payload),
            error_message=error_message,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def update_event_status(
        self,
        event: WebhookEvent,
        status: str,
        error_message: str | None = None,
    ) -> WebhookEvent:
        event.status = status
        event.error_message = error_message
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def extract_repository_url(self, payload: dict[str, Any]) -> str | None:
        repo = payload.get("repository") or {}
        return repo.get("html_url") or repo.get("clone_url")

    def extract_branch(self, event_type: str, payload: dict[str, Any]) -> str | None:
        if event_type == "push":
            ref = payload.get("ref", "")
            if ref.startswith("refs/heads/"):
                return ref.replace("refs/heads/", "", 1)
            return ref or None

        if event_type == "pull_request":
            pr = payload.get("pull_request") or {}
            head = pr.get("head") or {}
            return head.get("ref")

        return None

    def extract_changed_files(self, event_type: str, payload: dict[str, Any]) -> list[str]:
        if event_type == "push":
            changed = set()

            for commit in payload.get("commits", []):
                for key in ["added", "modified", "removed"]:
                    for path in commit.get(key, []):
                        if path:
                            changed.add(path)

            return sorted(changed)

        if event_type == "pull_request":
            action = payload.get("action")

            # Only process meaningful PR actions
            if action not in {"opened", "synchronize", "reopened"}:
                return []

            owner, repo = self.github_api_service.extract_owner_repo_from_payload(payload)
            pr_number = self.github_api_service.extract_pr_number(payload)

            if not owner or not repo or not pr_number:
                return []

            return self.github_api_service.get_pull_request_files(owner, repo, pr_number)

        return []
