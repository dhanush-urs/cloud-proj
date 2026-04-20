from apps.api.app.db.session import SessionLocal
from apps.api.app.db.models.file import File
from sqlalchemy import select
try:
    with SessionLocal() as db:
        q = select(File).where(File.repository_id == "cf3f7280-508d-4824-b0cd-8bae4021e07f")
        rows = list(db.scalars(q).all())
        print(f"Found {len(rows)} files for repo")
        for r in rows:
            print(f"  {r.path}")
except Exception as e:
    import traceback
    traceback.print_exc()
