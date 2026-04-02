import subprocess
from pathlib import Path


class GitSyncService:
    def sync_repository(self, local_path: str, branch: str | None = None) -> None:
        repo_path = Path(local_path)

        if not repo_path.exists():
            raise ValueError("Local repository path does not exist")

        if not (repo_path / ".git").exists():
            raise ValueError("Local repository path is not a git repository")

        self._run_git(["git", "fetch", "--all", "--prune"], repo_path)

        if branch:
            # Try checkout branch if it exists locally or remotely.
            self._run_git(["git", "checkout", branch], repo_path, allow_fail=True)
            self._run_git(["git", "pull", "origin", branch], repo_path, allow_fail=True)
        else:
            self._run_git(["git", "pull"], repo_path, allow_fail=True)

    def _run_git(self, cmd: list[str], cwd: Path, allow_fail: bool = False) -> None:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 and not allow_fail:
            raise ValueError(
                f"Git command failed: {' '.join(cmd)} | stderr={result.stderr.strip()}"
            )
