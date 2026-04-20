from pathlib import Path

from git import GitCommandError, Repo

from app.core.config import get_settings
from app.utils.ids import new_id

settings = get_settings()


def build_repo_local_path(repository_id: str) -> Path:
    base_path = Path(settings.REPO_STORAGE_ROOT)
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / repository_id


def clone_repository(repo_url: str, repository_id: str, branch: str | None = None) -> tuple[Path, str]:
    import shutil
    target_path = build_repo_local_path(repository_id)

    if target_path.exists():
        if (target_path / ".git").exists():
            # Try to open and fetch — if either fails the .git dir is corrupt.
            _fetch_ok = False
            try:
                repo = Repo(target_path)
                repo.remotes.origin.fetch("--all", "--prune")
                _fetch_ok = True
            except Exception:
                pass

            if not _fetch_ok:
                # Corrupted or incomplete .git — wipe entirely and re-clone.
                shutil.rmtree(target_path, ignore_errors=True)
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                # Fetch succeeded — remove stale non-git working-tree content.
                for child in target_path.iterdir():
                    if child.name == ".git":
                        continue
                    if child.is_file():
                        child.unlink()
                    else:
                        shutil.rmtree(child, ignore_errors=True)
    else:
        target_path.mkdir(parents=True, exist_ok=True)

    repo = None
    if not (target_path / ".git").exists():
        # First attempt: clone with specified branch
        if branch:
            try:
                repo = Repo.clone_from(repo_url, target_path, branch=branch)
            except GitCommandError as e:
                if "not found" in str(e).lower() or "did not match" in str(e).lower():
                    # Fallback: clone default branch
                    repo = Repo.clone_from(repo_url, target_path)
                else:
                    raise e
        else:
            repo = Repo.clone_from(repo_url, target_path)
    else:
        repo = Repo(target_path)
        try:
            repo.remotes.origin.fetch()
        except GitCommandError:
            pass # ignore fetch errors if we have local data

    if branch:
        try:
            repo.git.checkout(branch)
        except GitCommandError:
            # if branch checkout fails, stick with what we have (usually main/master)
            pass

    try:
        active_branch = repo.active_branch.name
    except (TypeError, Exception):
        # detached HEAD fallback
        active_branch = "HEAD"

    commit_sha = repo.head.commit.hexsha

    return target_path, commit_sha
