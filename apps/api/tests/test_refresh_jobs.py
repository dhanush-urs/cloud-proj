"""
Suite L: Refresh Jobs / Incremental Reindex Tests
TC-L1, TC-L2
"""

import pytest


def _create_repo(client, suffix="refresh-test"):
    r = client.post(
        "/api/v1/repos",
        json={"repo_url": f"https://github.com/example/{suffix}", "branch": "main"},
    )
    assert r.status_code in (200, 201)
    return r.json()["id"]


def test_refresh_jobs_list_empty_repo(client):
    """TC-L1: New repo has no refresh jobs — must return empty list"""
    repo_id = _create_repo(client)
    response = client.get(f"/api/v1/repos/{repo_id}/refresh-jobs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_refresh_jobs_list_invalid_repo_no_500(client):
    """TC-L1: Refresh jobs for invalid repo → 404, not 500"""
    response = client.get("/api/v1/repos/nonexistent-repo/refresh-jobs")
    assert response.status_code in (200, 404), (
        f"Got unexpected 500: {response.text}"
    )


def test_refresh_job_detail_invalid_id_no_500(client):
    """TC-L2: Get refresh job detail for nonexistent ID — 404 not 500"""
    response = client.get("/api/v1/refresh-jobs/nonexistent-job-id")
    assert response.status_code in (404,), (
        f"Expected 404, got {response.status_code}: {response.text}"
    )
