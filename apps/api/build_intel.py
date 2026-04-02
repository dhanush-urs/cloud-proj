from app.db.session import SessionLocal
from app.db.models.repository import Repository
from app.services.repo_intelligence_service import RepoIntelligenceService
from sqlalchemy import select

def build():
    db = SessionLocal()
    # Find fastapi
    repo = db.scalar(select(Repository).where(Repository.name == 'fastapi'))
    if repo:
        print(f"Building intelligence for {repo.name}...")
        service = RepoIntelligenceService(db)
        service.build_repo_intelligence(repo)
        print("Done.")
    else:
        print("fastapi repo not found")

if __name__ == "__main__":
    build()
