"""
Suite G: Ask Repo (RAG) Tests
TC-G1, TC-G2
"""


def _create_repo(client, suffix="ask-test"):
    r = client.post(
        "/api/v1/repos",
        json={"repo_url": f"https://github.com/example/{suffix}", "branch": "main"},
    )
    assert r.status_code in (200, 201)
    return r.json()["id"]


def test_ask_repo_no_embeddings_no_crash(client):
    """TC-G2: Ask with no indexed context → graceful fallback, not 500"""
    repo_id = _create_repo(client)
    response = client.post(
        f"/api/v1/repos/{repo_id}/ask",
        json={"question": "Which file handles API routing?", "top_k": 5},
    )
    assert response.status_code in (200, 409), (
        f"Got unexpected {response.status_code}: {response.text}"
    )
    if response.status_code == 200:
        data = response.json()
        assert "answer" in data


def test_ask_repo_empty_question_returns_422(client):
    """TC-G1: Empty question must fail validation"""
    repo_id = _create_repo(client, "ask-empty")
    response = client.post(
        f"/api/v1/repos/{repo_id}/ask",
        json={"question": "", "top_k": 5},
    )
    assert response.status_code in (400, 422), (
        f"Expected validation error, got {response.status_code}"
    )


def test_ask_repo_missing_question_422(client):
    """TC-G1: Missing question field → 422"""
    repo_id = _create_repo(client, "ask-missing")
    response = client.post(f"/api/v1/repos/{repo_id}/ask", json={"top_k": 5})
    assert response.status_code == 422
