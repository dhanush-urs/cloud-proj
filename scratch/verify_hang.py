from app.db.session import SessionLocal
from app.db.models.file import File
from sqlalchemy import select

db = SessionLocal()
# Select one of the parsing repos
repo_id = "3c771213-0c9f-4b79-a250-102527ea67b2"
files = db.execute(select(File).where(File.repository_id == repo_id)).scalars().all()
print(f"Total files: {len(files)}")
for f in sorted(files, key=lambda x: len(x.content or ""), reverse=True)[:5]:
    size = len(f.content or "")
    print(f"{f.path} - size: {size} - ext: {f.extension} - lang: {f.language}")
