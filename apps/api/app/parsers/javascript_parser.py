import re
from pathlib import Path


IMPORT_RE = re.compile(
    r"""^\s*import\s+(?:.+?\s+from\s+)?['"]([^'"]+)['"]\s*;?""",
    re.MULTILINE,
)

REQUIRE_RE = re.compile(
    r"""require\(\s*['"]([^'"]+)['"]\s*\)"""
)

CLASS_RE = re.compile(
    r"""^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)""",
    re.MULTILINE,
)

FUNCTION_RE = re.compile(
    r"""^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(""",
    re.MULTILINE,
)

ARROW_FUNCTION_RE = re.compile(
    r"""^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>""",
    re.MULTILINE,
)


class JavaScriptParser:
    language = "JavaScript/TypeScript"

    SUPPORTED_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> dict:
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return {
                "symbols": [],
                "dependencies": [],
                "error": f"Failed to read file: {exc}",
            }

        symbols = []
        dependencies = []

        lines = source.splitlines()

        # imports
        for match in IMPORT_RE.finditer(source):
            dependencies.append(
                {
                    "edge_type": "import",
                    "source_ref": None,
                    "target_ref": match.group(1),
                }
            )

        for match in REQUIRE_RE.finditer(source):
            dependencies.append(
                {
                    "edge_type": "require",
                    "source_ref": None,
                    "target_ref": match.group(1),
                }
            )

        # classes
        for match in CLASS_RE.finditer(source):
            name = match.group(1)
            line_no = self._line_number_from_index(source, match.start())
            symbols.append(
                {
                    "name": name,
                    "symbol_type": "class",
                    "signature": f"class {name}",
                    "start_line": line_no,
                    "end_line": line_no,
                }
            )

        # named functions
        for match in FUNCTION_RE.finditer(source):
            name = match.group(1)
            line_no = self._line_number_from_index(source, match.start())
            symbols.append(
                {
                    "name": name,
                    "symbol_type": "function",
                    "signature": f"function {name}(...)",
                    "start_line": line_no,
                    "end_line": line_no,
                }
            )

        # arrow functions
        for match in ARROW_FUNCTION_RE.finditer(source):
            name = match.group(1)
            line_no = self._line_number_from_index(source, match.start())
            symbols.append(
                {
                    "name": name,
                    "symbol_type": "arrow_function",
                    "signature": f"const {name} = (...) =>",
                    "start_line": line_no,
                    "end_line": line_no,
                }
            )

        # export detection
        EXPORT_RE = re.compile(r"export\s+(?:const|let|var|function|class)\s+([A-Za-z_][A-Za-z0-9_]*)")
        for match in EXPORT_RE.finditer(source):
            dependencies.append({
                "edge_type": "export",
                "source_ref": match.group(1),
                "target_ref": None
            })

        # basic call detection (e.g. someFunc())
        CALL_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        for match in CALL_RE.finditer(source):
            # filter out common keywords
            if match.group(1) not in {"if", "for", "while", "switch", "catch", "require", "import"}:
                dependencies.append({
                    "edge_type": "call",
                    "source_ref": None,
                    "target_ref": match.group(1)
                })

        return {
            "symbols": symbols,
            "dependencies": dependencies,
            "error": None,
        }

    def _line_number_from_index(self, source: str, index: int) -> int:
        return source.count("\n", 0, index) + 1
