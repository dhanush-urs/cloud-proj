from collections import deque

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.dependency_edge import DependencyEdge
from app.db.models.file import File
from app.scoring.impact_scoring import (
    classify_impact_level,
    compute_file_impact_score,
    compute_total_impact_score,
)
from app.services.risk_service import RiskService


class PRImpactService:
    def __init__(self, db: Session):
        self.db = db
        self.risk_service = RiskService(db)

    def analyze_impact(
        self,
        repository_id: str,
        changed_files: list[str],
        max_depth: int = 3,
    ) -> dict:
        all_files = list(
            self.db.scalars(
                select(File).where(File.repository_id == repository_id)
            ).all()
        )

        if not all_files:
            return self._empty_response(repository_id, changed_files)

        path_to_file = {f.path: f for f in all_files}
        file_map = {f.id: f for f in all_files}

        changed_file_records = [path_to_file[p] for p in changed_files if p in path_to_file]

        if not changed_file_records:
            return {
                "repository_id": repository_id,
                "changed_files": changed_files,
                "impacted_count": 0,
                "risk_level": "low",
                "total_impact_score": 0.0,
                "summary": "None of the provided changed files were found in the indexed repository.",
                "impacted_files": [],
                "reviewer_suggestions": [],
            }

        file_ids = [f.id for f in all_files]

        edges = list(
            self.db.scalars(
                select(DependencyEdge).where(
                    DependencyEdge.repository_id == repository_id,
                    DependencyEdge.from_file_id.in_(file_ids),
                    DependencyEdge.to_file_id.in_(file_ids),
                )
            ).all()
        )

        # Reverse adjacency:
        # If A imports B, then changing B can impact A
        reverse_adj: dict[str, set[str]] = {}
        forward_adj: dict[str, set[str]] = {}

        for edge in edges:
            if not edge.from_file_id or not edge.to_file_id:
                continue

            reverse_adj.setdefault(edge.to_file_id, set()).add(edge.from_file_id)
            forward_adj.setdefault(edge.from_file_id, set()).add(edge.to_file_id)

        inbound_counts = {
            file_id: len(reverse_adj.get(file_id, set()))
            for file_id in file_map.keys()
        }

        outbound_counts = {
            file_id: len(forward_adj.get(file_id, set()))
            for file_id in file_map.keys()
        }

        risk_map = self.risk_service.get_file_risk_map(repository_id)

        visited_depth: dict[str, int] = {}
        queue = deque()

        for file in changed_file_records:
            visited_depth[file.id] = 0
            queue.append((file.id, 0))

        while queue:
            current_file_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            for dependent_file_id in reverse_adj.get(current_file_id, set()):
                next_depth = depth + 1

                if dependent_file_id not in visited_depth or next_depth < visited_depth[dependent_file_id]:
                    visited_depth[dependent_file_id] = next_depth
                    queue.append((dependent_file_id, next_depth))

        impacted_files = []

        for file_id, depth in visited_depth.items():
            file = file_map[file_id]
            file_risk = risk_map.get(file_id, {})
            risk_score = float(file_risk.get("risk_score", 0.0))

            inbound = inbound_counts.get(file_id, 0)
            outbound = outbound_counts.get(file_id, 0)

            impact_score = compute_file_impact_score(
                depth=depth,
                inbound_dependencies=inbound,
                outbound_dependencies=outbound,
                risk_score=risk_score,
            )

            impacted_files.append(
                {
                    "file_id": file.id,
                    "path": file.path,
                    "language": file.language,
                    "depth": depth,
                    "inbound_dependencies": inbound,
                    "outbound_dependencies": outbound,
                    "risk_score": round(risk_score, 2),
                    "impact_score": impact_score,
                }
            )

        impacted_files.sort(key=lambda x: (x["depth"], -x["impact_score"], -x["risk_score"]))

        total_impact_score = compute_total_impact_score(
            [item["impact_score"] for item in impacted_files]
        )

        risk_level = classify_impact_level(total_impact_score)

        summary = self._build_summary(
            changed_files=changed_files,
            impacted_count=len(impacted_files),
            total_impact_score=total_impact_score,
            risk_level=risk_level,
        )

        reviewer_suggestions = self._suggest_reviewers(impacted_files)

        return {
            "repository_id": repository_id,
            "changed_files": changed_files,
            "impacted_count": len(impacted_files),
            "risk_level": risk_level,
            "total_impact_score": total_impact_score,
            "summary": summary,
            "impacted_files": impacted_files[:50],
            "reviewer_suggestions": reviewer_suggestions,
        }

    def _build_summary(
        self,
        changed_files: list[str],
        impacted_count: int,
        total_impact_score: float,
        risk_level: str,
    ) -> str:
        return (
            f"Analyzed {len(changed_files)} changed file(s). "
            f"Estimated blast radius touches {impacted_count} file(s). "
            f"Overall impact score is {total_impact_score:.2f}, classified as {risk_level} risk."
        )

    def _suggest_reviewers(self, impacted_files: list[dict]) -> list[dict]:
        suggestions = []
        seen = set()

        top_files = sorted(
            impacted_files,
            key=lambda x: x["impact_score"],
            reverse=True,
        )[:5]

        for item in top_files:
            path = item["path"]
            parts = path.split("/")

            hint = "core-owner"
            reason = f"High-impact file: {path}"

            if len(parts) >= 2:
                hint = f"{parts[0]}-{parts[1]}-owner"
            elif len(parts) == 1:
                hint = f"{parts[0]}-owner"

            if hint in seen:
                continue

            seen.add(hint)
            suggestions.append(
                {
                    "reviewer_hint": hint,
                    "reason": reason,
                }
            )

        return suggestions

    def _empty_response(self, repository_id: str, changed_files: list[str]) -> dict:
        return {
            "repository_id": repository_id,
            "changed_files": changed_files,
            "impacted_count": 0,
            "risk_level": "low",
            "total_impact_score": 0.0,
            "summary": "Repository has no indexed files.",
            "impacted_files": [],
            "reviewer_suggestions": [],
        }
