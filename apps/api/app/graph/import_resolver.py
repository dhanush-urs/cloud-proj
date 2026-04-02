from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.file import File


class ImportResolver:
    def __init__(self, db: Session):
        self.db = db

    def resolve_repository_imports(self, repository_id: str) -> int:
        files = list(
            self.db.scalars(
                select(File).where(File.repository_id == repository_id)
            ).all()
        )

        path_map = {file.path: file for file in files}
        filename_map = {}
        stem_map = {}

        for file in files:
            filename_map.setdefault(PurePosixPath(file.path).name, []).append(file)
            stem_map.setdefault(PurePosixPath(file.path).stem, []).append(file)

        from app.db.models.dependency_edge import DependencyEdge

        edges = list(
            self.db.scalars(
                select(DependencyEdge).where(
                    DependencyEdge.repository_id == repository_id,
                    DependencyEdge.source_file_id.is_not(None),
                )
            ).all()
        )

        resolved_count = 0

        for edge in edges:
            if edge.target_file_id:
                continue

            target_ref = edge.target_ref
            if not target_ref:
                continue

            resolved = self._resolve_target(target_ref, path_map, filename_map, stem_map)

            if resolved:
                edge.target_file_id = resolved.id
                resolved_count += 1

        self.db.commit()
        return resolved_count

    def _resolve_target(self, target_ref: str, path_map: dict, filename_map: dict, stem_map: dict):
        # 1) exact path match
        if target_ref in path_map:
            return path_map[target_ref]

        # 2) python-style dotted path -> convert to path
        python_candidate = target_ref.replace(".", "/")
        python_variants = [
            f"{python_candidate}.py",
            f"{python_candidate}/__init__.py",
        ]

        for candidate in python_variants:
            if candidate in path_map:
                return path_map[candidate]

        # 3) JS relative-ish / package-ish basename match
        target_name = PurePosixPath(target_ref).name

        js_variants = [
            target_ref,
            f"{target_ref}.js",
            f"{target_ref}.jsx",
            f"{target_ref}.ts",
            f"{target_ref}.tsx",
            f"{target_ref}/index.js",
            f"{target_ref}/index.ts",
        ]

        for candidate in js_variants:
            if candidate in path_map:
                return path_map[candidate]

        # 4) basename fallback
        if target_name in filename_map and len(filename_map[target_name]) == 1:
            return filename_map[target_name][0]

        # 5) stem fallback
        stem = PurePosixPath(target_ref).stem or target_ref.split(".")[-1]
        if stem in stem_map and len(stem_map[stem]) == 1:
            return stem_map[stem][0]

        return None
