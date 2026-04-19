from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models.repo_job import RepoJob


class JobService:
    """
    Manages job lifecycle using the canonical RepoJob model.
    
    IMPORTANT: Tasks (tasks_ingest, tasks_parse, tasks_embed) all use RepoJob.
    This service must use the same model so job IDs match between API and task runner.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self,
        repository_id: str,
        job_type: str,
        status: str = "queued",
        message: str | None = None,
    ) -> RepoJob:
        job = RepoJob(
            repository_id=repository_id,
            job_type=job_type,
            status=status,
            message=message,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_task_id(self, job_id: str, task_id: str) -> RepoJob | None:
        job = self.db.get(RepoJob, job_id)
        if not job:
            return None
        job.task_id = str(task_id)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, repository_id: str | None = None) -> tuple[list[RepoJob], int]:
        stmt = select(RepoJob)

        if repository_id:
            stmt = stmt.where(RepoJob.repository_id == repository_id)

        stmt = stmt.order_by(desc(RepoJob.created_at))
        jobs = list(self.db.scalars(stmt).all())
        return jobs, len(jobs)
