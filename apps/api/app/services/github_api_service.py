from typing import Any

import requests

from app.core.config import get_settings

settings = get_settings()


class GitHubAPIService:
    def __init__(self):
        self.token = settings.GITHUB_TOKEN

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoBrain/1.0",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[str]:
        files = []
        page = 1

        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
            response = requests.get(
                url,
                headers=self._headers(),
                params={"per_page": 100, "page": page},
                timeout=20,
            )

            if response.status_code >= 400:
                raise ValueError(
                    f"GitHub API error while fetching PR files: {response.status_code} {response.text}"
                )

            data = response.json()
            if not data:
                break

            for item in data:
                filename = item.get("filename")
                if filename:
                    files.append(filename)

            if len(data) < 100:
                break

            page += 1

        return sorted(set(files))

    def extract_owner_repo_from_payload(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        repo_data = payload.get("repository") or {}
        full_name = repo_data.get("full_name")

        if full_name and "/" in full_name:
            owner, repo = full_name.split("/", 1)
            return owner, repo

        return None, None

    def extract_pr_number(self, payload: dict[str, Any]) -> int | None:
        pr = payload.get("pull_request") or {}
        return pr.get("number")
