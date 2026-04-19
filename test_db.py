import sys
sys.path.insert(0, 'apps/api')
from app.db.session import SessionLocal
from app.db.models.repo_job import RepoJob

try:
    db = SessionLocal()
    for j in db.query(RepoJob).order_by(RepoJob.created_at.desc()).limit(1).all():
        print(f"STATUS: {j.status}")
        print(f"ERROR DETAILS: {j.error_details}")
        print(f"MESSAGE: {j.message}")
        print("==========")
except Exception as e:
    print(f"Could not connect: {e}")
