import json
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.db.models.repository import Repository
from app.db.models.repo_intelligence import RepoIntelligence
from app.db.models.file import File

engine = create_engine(get_settings().DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

repos = db.scalars(select(Repository)).all()
print(f"Total repos: {len(repos)}")

for repo in repos:
    print(f"\n--- REPO: {repo.name} (id: {repo.id}) ---")
    
    intel = db.scalar(select(RepoIntelligence).where(RepoIntelligence.repository_id == repo.id))
    if intel:
        print("✅ RepoIntelligence found:")
        print(f"  - repo_summary_text length: {len(intel.repo_summary_text or '')}")
        print(f"  - architecture_summary_text length: {len(intel.architecture_summary_text or '')}")
        print(f"  - top_level_dirs: {intel.top_level_dirs}")
        print(f"  - api_routes_summary length: {len(intel.api_routes_summary or '')}")
        print(f"  - frameworks length: {len(intel.frameworks or '')}")
    else:
        print("❌ No RepoIntelligence found")

    # Check files
    enriched_files = db.scalars(
        select(File).where(File.repository_id == repo.id, File.summary_text.is_not(None)).limit(3)
    ).all()
    
    print(f"\nEnriched files found: {len(enriched_files)} (showing up to 3)")
    for f in enriched_files:
        print(f"  ✅ {f.path}:")
        print(f"     - summary_text length: {len(f.summary_text or '')}")
        print(f"     - importance_score: {f.importance_score}")
        print(f"     - line_count: {f.line_count}")

db.close()
