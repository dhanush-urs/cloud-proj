from pathlib import Path


class Chunker:
    def __init__(self, max_lines: int = 80, overlap: int = 15):
        self.max_lines = max_lines
        self.overlap = overlap

    def chunk_file(self, file_path: Path) -> list[dict]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        lines = text.splitlines()

        if not lines:
            return []

        chunks = []
        start = 0

        while start < len(lines):
            end = min(start + self.max_lines, len(lines))
            chunk_lines = lines[start:end]
            content = "\n".join(chunk_lines).strip()

            if content:
                chunks.append(
                    {
                        "chunk_type": "code_window",
                        "content": content,
                        "start_line": start + 1,
                        "end_line": end,
                    }
                )

            if end >= len(lines):
                break

            start = max(start + self.max_lines - self.overlap, start + 1)

        return chunks
