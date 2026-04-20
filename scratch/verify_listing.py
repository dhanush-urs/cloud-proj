from app.db.session import SessionLocal
from app.services.file_service import FileService
from app.db.models.repository import Repository
import traceback

db = SessionLocal()
try:
    repo = db.query(Repository).order_by(Repository.created_at.desc()).first()
    print("Repo:", repo.name, repo.status)
    fs = FileService(db)
    files = fs.list_files(repo.id)
    print("Filtered Files returned:", len(files))
except Exception as e:
    traceback.print_exc()
finally:
    db.close()
