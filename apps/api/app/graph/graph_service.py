from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.dependency_edge import DependencyEdge
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.models.symbol import Symbol
from app.graph.import_resolver import ImportResolver
from app.graph.neo4j_client import Neo4jClient


class GraphService:
    def __init__(self, db: Session):
        self.db = db
        try:
            self.neo4j = Neo4jClient()
            self._neo4j_error: str | None = None
        except RuntimeError as exc:
            self.neo4j = None  # type: ignore[assignment]
            self._neo4j_error = str(exc)

    def _require_neo4j(self):
        """Raise a legible error if neo4j is unavailable. Call at the start of any neo4j method."""
        if self.neo4j is None:
            raise RuntimeError(self._neo4j_error or "Neo4j is unavailable in this environment.")

    def close(self):
        if self.neo4j is not None:
            self.neo4j.close()

    def sync_repository_graph(self, repository: Repository) -> dict:
        self._require_neo4j()
        try:
            resolver = ImportResolver(self.db)
            resolved_imports = resolver.resolve_repository_imports(repository.id)

            files = list(
                self.db.scalars(
                    select(File).where(File.repository_id == repository.id)
                ).all()
            )

            symbols = list(
                self.db.scalars(
                    select(Symbol).where(Symbol.repository_id == repository.id)
                ).all()
            )

            edges = list(
                self.db.scalars(
                    select(DependencyEdge).where(DependencyEdge.repository_id == repository.id)
                ).all()
            )

            self._ensure_constraints()

            self._upsert_repository_node(repository)
            self._clear_repository_subgraph(repository.id)
            self._upsert_repository_node(repository)

            for file_record in files:
                self._upsert_file_node(repository.id, file_record)
                self._link_repo_to_file(repository.id, file_record.id)

            for symbol in symbols:
                self._upsert_symbol_node(repository.id, symbol)
                self._link_file_to_symbol(symbol.file_id, symbol.id)

            internal_import_edges = 0
            external_import_edges = 0

            for edge in edges:
                if edge.source_file_id and edge.target_file_id:
                    self._link_file_import_to_file(
                        edge.source_file_id,
                        edge.target_file_id,
                        edge.edge_type,
                        edge.source_ref,
                        edge.target_ref,
                    )
                    internal_import_edges += 1
                elif edge.source_file_id:
                    self._link_file_import_external(
                        edge.source_file_id,
                        edge.edge_type,
                        edge.source_ref,
                        edge.target_ref,
                    )
                    external_import_edges += 1

            return {
                "repository_id": repository.id,
                "files_synced": len(files),
                "symbols_synced": len(symbols),
                "dependency_edges_synced": len(edges),
                "resolved_imports": resolved_imports,
                "internal_import_edges": internal_import_edges,
                "external_import_edges": external_import_edges,
            }
        finally:
            self.close()

    def get_repository_graph_summary(self, repository_id: str) -> dict:
        self._require_neo4j()
        try:
            query = """
            MATCH (r:Repository {id: $repository_id})
            OPTIONAL MATCH (r)-[:HAS_FILE]->(f:File)
            OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
            OPTIONAL MATCH (f)-[i:IMPORTS]->(:File)
            OPTIONAL MATCH (f)-[e:IMPORTS_EXTERNAL]->(:ExternalImport)
            RETURN
              r.id AS repository_id,
              count(DISTINCT f) AS file_count,
              count(DISTINCT s) AS symbol_count,
              count(DISTINCT i) AS internal_import_count,
              count(DISTINCT e) AS external_import_count
            """
            rows = self.neo4j.execute_read(query, {"repository_id": repository_id})

            if not rows:
                return {
                    "repository_id": repository_id,
                    "file_count": 0,
                    "symbol_count": 0,
                    "internal_import_count": 0,
                    "external_import_count": 0,
                }

            row = rows[0]
            return {
                "repository_id": row["repository_id"],
                "file_count": row["file_count"],
                "symbol_count": row["symbol_count"],
                "internal_import_count": row["internal_import_count"],
                "external_import_count": row["external_import_count"],
            }
        finally:
            self.close()

    def _ensure_constraints(self):
        queries = [
            "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT symbol_id_unique IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT external_import_key_unique IF NOT EXISTS FOR (e:ExternalImport) REQUIRE e.key IS UNIQUE",
        ]

        for query in queries:
            self.neo4j.execute_write(query)

    def _clear_repository_subgraph(self, repository_id: str):
        query = """
        MATCH (r:Repository {id: $repository_id})
        OPTIONAL MATCH (r)-[:HAS_FILE]->(f:File)
        OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
        OPTIONAL MATCH (f)-[ri:IMPORTS]->(:File)
        OPTIONAL MATCH (f)-[re:IMPORTS_EXTERNAL]->(:ExternalImport)
        DETACH DELETE f, s
        """
        self.neo4j.execute_write(query, {"repository_id": repository_id})

    def _upsert_repository_node(self, repository: Repository):
        query = """
        MERGE (r:Repository {id: $id})
        SET r.name = $name,
            r.full_name = $full_name,
            r.repo_url = $repo_url,
            r.provider = $provider,
            r.status = $status,
            r.primary_language = $primary_language,
            r.default_branch = $default_branch
        """
        self.neo4j.execute_write(
            query,
            {
                "id": repository.id,
                "name": repository.name,
                "full_name": repository.full_name,
                "repo_url": repository.repo_url,
                "provider": repository.provider,
                "status": repository.status,
                "primary_language": repository.primary_language,
                "default_branch": repository.default_branch,
            },
        )

    def _upsert_file_node(self, repository_id: str, file_record: File):
        query = """
        MERGE (f:File {id: $id})
        SET f.repository_id = $repository_id,
            f.path = $path,
            f.language = $language,
            f.extension = $extension,
            f.file_kind = $file_kind,
            f.size_bytes = $size_bytes,
            f.line_count = $line_count,
            f.is_generated = $is_generated,
            f.is_test = $is_test,
            f.is_config = $is_config,
            f.is_doc = $is_doc,
            f.is_vendor = $is_vendor,
            f.parse_status = $parse_status
        """
        self.neo4j.execute_write(
            query,
            {
                "id": file_record.id,
                "repository_id": repository_id,
                "path": file_record.path,
                "language": file_record.language,
                "extension": file_record.extension,
                "file_kind": file_record.file_kind,
                "size_bytes": file_record.size_bytes,
                "line_count": file_record.line_count,
                "is_generated": file_record.is_generated,
                "is_test": file_record.is_test,
                "is_config": file_record.is_config,
                "is_doc": file_record.is_doc,
                "is_vendor": file_record.is_vendor,
                "parse_status": file_record.parse_status,
            },
        )

    def _link_repo_to_file(self, repository_id: str, file_id: str):
        query = """
        MATCH (r:Repository {id: $repository_id})
        MATCH (f:File {id: $file_id})
        MERGE (r)-[:HAS_FILE]->(f)
        """
        self.neo4j.execute_write(query, {"repository_id": repository_id, "file_id": file_id})

    def _upsert_symbol_node(self, repository_id: str, symbol: Symbol):
        query = """
        MERGE (s:Symbol {id: $id})
        SET s.repository_id = $repository_id,
            s.file_id = $file_id,
            s.name = $name,
            s.symbol_type = $symbol_type,
            s.signature = $signature,
            s.start_line = $start_line,
            s.end_line = $end_line
        """
        self.neo4j.execute_write(
            query,
            {
                "id": symbol.id,
                "repository_id": repository_id,
                "file_id": symbol.file_id,
                "name": symbol.name,
                "symbol_type": symbol.symbol_type,
                "signature": symbol.signature,
                "start_line": symbol.start_line,
                "end_line": symbol.end_line,
            },
        )

    def _link_file_to_symbol(self, file_id: str, symbol_id: str):
        query = """
        MATCH (f:File {id: $file_id})
        MATCH (s:Symbol {id: $symbol_id})
        MERGE (f)-[:DEFINES]->(s)
        """
        self.neo4j.execute_write(query, {"file_id": file_id, "symbol_id": symbol_id})

    def _link_file_import_to_file(
        self,
        source_file_id: str,
        target_file_id: str,
        edge_type: str,
        source_ref: str | None,
        target_ref: str | None,
    ):
        query = """
        MATCH (src:File {id: $source_file_id})
        MATCH (dst:File {id: $target_file_id})
        MERGE (src)-[r:IMPORTS {edge_type: $edge_type, target_ref: $target_ref}]->(dst)
        SET r.source_ref = $source_ref
        """
        self.neo4j.execute_write(
            query,
            {
                "source_file_id": source_file_id,
                "target_file_id": target_file_id,
                "edge_type": edge_type,
                "source_ref": source_ref,
                "target_ref": target_ref,
            },
        )

    def _link_file_import_external(
        self,
        source_file_id: str,
        edge_type: str,
        source_ref: str | None,
        target_ref: str | None,
    ):
        external_key = f"{edge_type}:{target_ref or 'unknown'}"

        query = """
        MATCH (src:File {id: $source_file_id})
        MERGE (ext:ExternalImport {key: $external_key})
        SET ext.name = $target_ref,
            ext.edge_type = $edge_type
        MERGE (src)-[r:IMPORTS_EXTERNAL {edge_type: $edge_type, target_ref: $target_ref}]->(ext)
        SET r.source_ref = $source_ref
        """
        self.neo4j.execute_write(
            query,
            {
                "source_file_id": source_file_id,
                "external_key": external_key,
                "target_ref": target_ref,
                "edge_type": edge_type,
                "source_ref": source_ref,
            },
        )
