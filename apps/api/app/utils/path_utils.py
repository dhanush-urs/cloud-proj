"""Path utilities for normalize repository snapshot paths."""
from pathlib import Path


def normalize_repo_snapshot_path(local_path: str | None) -> Path | None:
    """
    Normalize a repo snapshot local_path string into a Path object.

    Returns None if local_path is None or empty.
    """
    if not local_path:
        return None
    return Path(local_path)
