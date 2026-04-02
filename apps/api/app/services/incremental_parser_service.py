import ast
import re
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.dependency_edge import DependencyEdge
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.models.symbol import Symbol


class IncrementalParserService:
    def __init__(self, db: Session):
        self.db = db

    def reparse_file(self, repository: Repository, file_row: File) -> None:
        self._delete_existing_parse_artifacts(file_row)

        content = file_row.content or ""
        path = file_row.path or ""
        language = (file_row.language or "").lower()

        symbols = self._extract_symbols(path, language, content)
        imports = self._extract_imports(path, language, content)

        for symbol in symbols:
            self.db.add(
                Symbol(
                    repository_id=repository.id,
                    file_id=file_row.id,
                    name=symbol["name"],
                    symbol_type=symbol["kind"],
                    start_line=symbol["start_line"],
                    end_line=symbol["end_line"],
                )
            )

        # Rebuild outbound dependency edges (best-effort path mapping)
        for imported_path in imports:
            target_file = self._resolve_import_to_file(repository.id, imported_path)
            if not target_file:
                continue

            self.db.add(
                DependencyEdge(
                    repository_id=repository.id,
                    source_file_id=file_row.id,
                    target_file_id=target_file.id,
                    edge_type="import",
                )
            )

        self.db.commit()

    def _delete_existing_parse_artifacts(self, file_row: File) -> None:
        self.db.execute(
            delete(Symbol).where(
                Symbol.repository_id == file_row.repository_id,
                Symbol.file_id == file_row.id,
            )
        )

        self.db.execute(
            delete(DependencyEdge).where(
                DependencyEdge.repository_id == file_row.repository_id,
                (DependencyEdge.source_file_id == file_row.id) | (DependencyEdge.target_file_id == file_row.id),
            )
        )

        self.db.commit()

    def _extract_symbols(self, path: str, language: str, content: str) -> list[dict]:
        if language == "python" or path.endswith(".py"):
            return self._extract_python_symbols(content)

        if language in {"javascript", "typescript", "tsx", "jsx"} or any(
            path.endswith(ext) for ext in [".js", ".ts", ".tsx", ".jsx"]
        ):
            return self._extract_js_ts_symbols(content)

        if language == "java" or path.endswith(".java"):
            return self._extract_java_symbols(content)

        return []

    def _extract_imports(self, path: str, language: str, content: str) -> list[str]:
        if language == "python" or path.endswith(".py"):
            return self._extract_python_imports(content)

        if language in {"javascript", "typescript", "tsx", "jsx"} or any(
            path.endswith(ext) for ext in [".js", ".ts", ".tsx", ".jsx"]
        ):
            return self._extract_js_ts_imports(content)

        if language == "java" or path.endswith(".java"):
            return self._extract_java_imports(content)

        return []

    def _extract_python_symbols(self, content: str) -> list[dict]:
        try:
            tree = ast.parse(content)
        except Exception:
            return []

        symbols = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "kind": "function",
                        "start_line": getattr(node, "lineno", 1),
                        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    }
                )
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "kind": "async_function",
                        "start_line": getattr(node, "lineno", 1),
                        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    }
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    {
                        "name": node.name,
                        "kind": "class",
                        "start_line": getattr(node, "lineno", 1),
                        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    }
                )

        return symbols

    def _extract_python_imports(self, content: str) -> list[str]:
        try:
            tree = ast.parse(content)
        except Exception:
            return []

        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.replace(".", "/"))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.replace(".", "/"))

        return list(sorted(set(imports)))

    def _extract_js_ts_symbols(self, content: str) -> list[dict]:
        patterns = [
            (r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", "function"),
            (r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*", "class"),
            (r"const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(", "function_like"),
            (r"export\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", "function"),
        ]

        lines = content.splitlines()
        symbols = []

        for idx, line in enumerate(lines, start=1):
            for pattern, kind in patterns:
                match = re.search(pattern, line)
                if match:
                    symbols.append(
                        {
                            "name": match.group(1),
                            "kind": kind,
                            "start_line": idx,
                            "end_line": idx,
                        }
                    )

        return symbols

    def _extract_js_ts_imports(self, content: str) -> list[str]:
        imports = set()

        patterns = [
            r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]',
            r'require\([\'"](.+?)[\'"]\)',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                imports.add(match.group(1))

        return sorted(imports)

    def _extract_java_symbols(self, content: str) -> list[dict]:
        lines = content.splitlines()
        symbols = []

        class_pattern = r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"
        method_pattern = r"(public|private|protected)?\s*(static\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("

        for idx, line in enumerate(lines, start=1):
            class_match = re.search(class_pattern, line)
            if class_match:
                symbols.append(
                    {
                        "name": class_match.group(1),
                        "kind": "class",
                        "start_line": idx,
                        "end_line": idx,
                    }
                )

            method_match = re.search(method_pattern, line)
            if method_match:
                symbols.append(
                    {
                        "name": method_match.group(3),
                        "kind": "method",
                        "start_line": idx,
                        "end_line": idx,
                    }
                )

        return symbols

    def _extract_java_imports(self, content: str) -> list[str]:
        imports = set()

        for match in re.finditer(r"import\s+([A-Za-z0-9_.]+);", content):
            imports.add(match.group(1).replace(".", "/"))

        return sorted(imports)

    def _resolve_import_to_file(self, repository_id: str, imported_path: str) -> File | None:
        candidates = [
            imported_path,
            f"{imported_path}.py",
            f"{imported_path}.js",
            f"{imported_path}.ts",
            f"{imported_path}.tsx",
            f"{imported_path}.jsx",
            f"{imported_path}.java",
            f"{imported_path}/__init__.py",
            f"{imported_path}/index.js",
            f"{imported_path}/index.ts",
        ]

        for candidate in candidates:
            file_row = self.db.scalar(
                select(File).where(
                    File.repository_id == repository_id,
                    File.path == candidate,
                )
            )
            if file_row:
                return file_row

        # fallback: suffix match (best-effort, can be ambiguous)
        for candidate in candidates:
            file_row = self.db.scalar(
                select(File).where(
                    File.repository_id == repository_id,
                    File.path.like(f"%{candidate}")
                )
            )
            if file_row:
                return file_row

        return None
