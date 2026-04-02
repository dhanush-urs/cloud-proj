from __future__ import annotations
import logging
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.db.models.dependency_edge import DependencyEdge
from app.db.models.file import File
from app.db.models.symbol import Symbol

logger = logging.getLogger(__name__)

class GraphService:
    def __init__(self, db: Session):
        self.db = db

    def resolve_repository_dependencies(self, repository_id: str):
        """
        Attempts to resolve all string-based DependencyEdge.target_ref to actual File.id or Symbol.id.
        This is a post-parsing enrichment step.
        """
        edges = list(self.db.scalars(
            select(DependencyEdge).where(
                DependencyEdge.repository_id == repository_id,
                DependencyEdge.target_file_id == None
            )
        ).all())

        if not edges:
            return 0

        # Pre-fetch all file paths for this repo for faster lookup
        files = list(self.db.scalars(
            select(File).where(File.repository_id == repository_id)
        ).all())
        
        # Map of partial paths and module names to file IDs
        # e.g., "app/utils.py" -> ID, "app.utils" -> ID
        path_to_id = {}
        for f in files:
            path_to_id[f.path] = f.id
            if f.path.endswith(".py"):
                mod_name = f.path.replace(".py", "").replace("/", ".")
                path_to_id[mod_name] = f.id
            if f.path.endswith(".js") or f.path.endswith(".ts") or f.path.endswith(".tsx"):
                mod_name = f.path.rsplit(".", 1)[0]
                path_to_id[mod_name] = f.id

        resolved_count = 0
        for edge in edges:
            ref = edge.target_ref
            if not ref:
                continue
            
            # Simple exact match or module match
            target_id = path_to_id.get(ref)
            
            # Try relative path resolution if possible? 
            # (Skipping deep relative resolution for MVP)
            
            if target_id:
                edge.target_file_id = target_id
                resolved_count += 1
        
        self.db.commit()
        return resolved_count

    def get_incoming_dependencies(self, file_id: str) -> list[DependencyEdge]:
        """Find all files that depend on this file."""
        return list(self.db.scalars(
            select(DependencyEdge).where(DependencyEdge.target_file_id == file_id)
        ).all())

    def get_outgoing_dependencies(self, file_id: str) -> list[DependencyEdge]:
        """Find all files this file depends on."""
        return list(self.db.scalars(
            select(DependencyEdge).where(DependencyEdge.source_file_id == file_id)
        ).all())

    def get_symbol_usage(self, repository_id: str, symbol_name: str) -> list[DependencyEdge]:
        """Find where a symbol (function/class name) is called."""
        return list(self.db.scalars(
            select(DependencyEdge).where(
                DependencyEdge.repository_id == repository_id,
                DependencyEdge.edge_type == "call",
                DependencyEdge.target_ref == symbol_name
            )
        ).all())
