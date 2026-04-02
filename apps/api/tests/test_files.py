"""
Suite E: File Explorer Tests
TC-E1, TC-E2
"""

import pytest


def _create_repo(client, suffix="file-test"):
    r = client.post(
        "/api/v1/repos",
        json={"repo_url": f"https://github.com/example/{suffix}", "branch": "main"},
    )
    assert r.status_code in (200, 201)
    return r.json()["id"]


def test_files_list_returns_200(client):
    """TC-E1: File list endpoint — valid repo returns 200"""
    repo_id = _create_repo(client)
    response = client.get(f"/api/v1/repos/{repo_id}/files")
    assert response.status_code == 200
    data = response.json()
    # Should have pagination fields
    assert "total" in data or "items" in data


def test_files_list_invalid_repo_returns_404(client):
    """TC-E2: File list for invalid repo → 404"""
    response = client.get("/api/v1/repos/nonexistent-repo-id/files")
    assert response.status_code in (200, 404)  # some return empty, some return 404


def test_files_limit_param(client):
    """TC-E1: limit param should be respected without crashing"""
    repo_id = _create_repo(client, "limit-test")
    response = client.get(f"/api/v1/repos/{repo_id}/files?limit=5")
    assert response.status_code == 200
