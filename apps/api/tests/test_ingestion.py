"""
Suite D: Ingestion / Parse / Embed Workflow Precondition Tests
TC-D2, TC-D3, TC-D4 — Tests for graceful precondition enforcement.
"""

import pytest


def _create_repo(client, suffix="workflow"):
    payload = {
        "repo_url": f"https://github.com/example/{suffix}-repo",
        "branch": "main",
    }
    r = client.post("/api/v1/repos", json=payload)
    assert r.status_code in (200, 201)
    return r.json()["id"]


def test_parse_registered_repo_no_crash(client):
    """TC-D2: Parse route should not throw 500 even if repo isn't cloned"""
    repo_id = _create_repo(client, "parse-test")
    response = client.post(f"/api/v1/repos/{repo_id}/parse")
    # Must be 200/202 (queued) OR 409 (precondition not met), never 500
    assert response.status_code in (200, 202, 409), (
        f"Unexpected status {response.status_code}: {response.text}"
    )


def test_parse_nonexistent_repo_returns_404(client):
    """TC-C4 / TC-D2: Parse on unknown repo → 404"""
    response = client.post("/api/v1/repos/unknown-repo-xyz/parse")
    assert response.status_code == 404


def test_embed_registered_repo_no_crash(client):
    """TC-D3: Embed route should not throw 500 even without parsed files"""
    repo_id = _create_repo(client, "embed-test")
    response = client.post(f"/api/v1/repos/{repo_id}/embed")
    # Must be 200/202 (queued) OR 409 (precondition not met), never 500
    assert response.status_code in (200, 202, 400, 409), (
        f"Unexpected status {response.status_code}: {response.text}"
    )


def test_embed_nonexistent_repo_returns_404(client):
    """TC-C4 / TC-D3: Embed on unknown repo → 404"""
    response = client.post("/api/v1/repos/unknown-repo-xyz/embed")
    assert response.status_code == 404
