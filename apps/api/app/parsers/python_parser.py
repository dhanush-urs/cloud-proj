import ast
from pathlib import Path


class PythonParser:
    language = "Python"

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".py"

    def parse(self, file_path: Path) -> dict:
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return {
                "symbols": [],
                "dependencies": [],
                "error": f"Failed to read file: {exc}",
            }

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {
                "symbols": [],
                "dependencies": [],
                "error": f"Python syntax error: {exc}",
            }

        symbols = []
        dependencies = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "symbol_type": "function",
                        "signature": self._build_function_signature(node),
                        "start_line": getattr(node, "lineno", 0),
                        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                    }
                )

            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(
                    {
                        "name": node.name,
                        "symbol_type": "async_function",
                        "signature": self._build_function_signature(node, async_fn=True),
                        "start_line": getattr(node, "lineno", 0),
                        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        "summary": ast.get_docstring(node),
                    }
                )

            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    {
                        "name": node.name,
                        "symbol_type": "class",
                        "signature": self._build_class_signature(node),
                        "start_line": getattr(node, "lineno", 0),
                        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        "summary": ast.get_docstring(node),
                    }
                )

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(
                        {
                            "edge_type": "import",
                            "source_ref": None,
                            "target_ref": alias.name,
                        }
                    )

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    full_target = f"{module_name}.{alias.name}" if module_name else alias.name
                    dependencies.append(
                        {
                            "edge_type": "from_import",
                            "source_ref": module_name or None,
                            "target_ref": full_target,
                        }
                    )

            elif isinstance(node, ast.Call):
                # Simple call-site detection
                if isinstance(node.func, ast.Name):
                    dependencies.append(
                        {
                            "edge_type": "call",
                            "source_ref": None, # Will be resolved if nested in function
                            "target_ref": node.func.id,
                        }
                    )
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    dependencies.append(
                        {
                            "edge_type": "call",
                            "source_ref": node.func.value.id,
                            "target_ref": node.func.attr,
                        }
                    )

        return {
            "symbols": symbols,
            "dependencies": dependencies,
            "error": None,
        }

    def _build_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef, async_fn: bool = False) -> str:
        arg_names = [arg.arg for arg in node.args.args]
        prefix = "async def" if async_fn else "def"
        return f"{prefix} {node.name}({', '.join(arg_names)})"

    def _build_class_signature(self, node: ast.ClassDef) -> str:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)

        if bases:
            return f"class {node.name}({', '.join(bases)})"
        return f"class {node.name}"
