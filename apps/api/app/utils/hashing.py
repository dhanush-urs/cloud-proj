import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    hasher = hashlib.sha256()

    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None
