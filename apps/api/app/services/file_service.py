from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.file import File


class FileService:
    def __init__(self, db: Session):
        self.db = db

    def list_files(self, repository_id: str, limit: int = 100) -> list[File]:
        return list(
            self.db.scalars(
                select(File)
                .where(File.repository_id == repository_id)
                .order_by(File.path.asc())
                .limit(limit)
            ).all()
        )

    def get_file(self, repository_id: str, file_id: str) -> File | None:
        return self.db.scalar(
            select(File).where(
                File.repository_id == repository_id,
                File.id == file_id,
            )
        )
