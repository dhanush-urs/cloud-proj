"""
Suite F: Semantic Search Tests
TC-F1, TC-F2, TC-F3
"""


def _create_repo(client, suffix="search-test"):
    r = client.post(
        "/api/v1/repos",
        json={"repo_url": f"https://github.com/example/{suffix}", "branch": "main"},
    )
    assert r.status_code in (200, 201)
    return r.json()["id"]


def test_search_empty_query_returns_422(client):
    """TC-F2: Empty query must fail validation with 422"""
    repo_id = _create_repo(client)
    response = client.post(
        f"/api/v1/repos/{repo_id}/search",
        json={"query": "", "top_k": 5},
    )
    # Must be 422 or at least not 500
    assert response.status_code in (400, 422), (
        f"Expected validation error, got {response.status_code}: {response.text}"
    )


def test_search_valid_query_no_crash(client):
    """TC-F3: Search before embeddings — must return empty or 409, not 500"""
    repo_id = _create_repo(client, "search-no-embed")
    response = client.post(
        f"/api/v1/repos/{repo_id}/search",
        json={"query": "Where is app initialization done?", "top_k": 5},
    )
    assert response.status_code in (200, 409), (
        f"Expected graceful response, got {response.status_code}: {response.text}"
    )
    if response.status_code == 200:
        data = response.json()
        assert "items" in data or "results" in data


def test_search_missing_query_returns_422(client):
    """TC-F2: Missing query field → 422"""
    repo_id = _create_repo(client, "search-missing")
    response = client.post(f"/api/v1/repos/{repo_id}/search", json={"top_k": 5})
    assert response.status_code == 422


def test_search_invalid_repo_no_crash(client):
    """TC-F1: Search on invalid repo must not return 500"""
    response = client.post(
        "/api/v1/repos/nonexistent-id/search",
        json={"query": "test query"},
    )
    assert response.status_code in (200, 404, 409, 422), (
        f"Got unexpected 500: {response.text}"
    )
