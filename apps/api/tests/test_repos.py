"""
Suite C: Core API Contract Tests — Repositories
TC-C2, TC-C3, TC-C4
"""

# --- TC-C2: Create repository ---
def test_create_repository(client):
    payload = {"repo_url": "https://github.com/example/test-repo", "branch": "main"}
    response = client.post("/api/v1/repos", json=payload)
    assert response.status_code in (200, 201)
    data = response.json()
    assert "id" in data
    assert data["repo_url"] == payload["repo_url"]
    assert data["branch"] == payload["branch"]


def test_create_repository_missing_url(client):
    """TC-C2: Malformed request should return 422"""
    response = client.post("/api/v1/repos", json={"branch": "main"})
    assert response.status_code == 422


def test_create_repository_duplicate_url(client):
    """TC-C2: Duplicate repos should fail gracefully (400 not 500)"""
    payload = {"repo_url": "https://github.com/example/dupe-repo", "branch": "main"}
    r1 = client.post("/api/v1/repos", json=payload)
    r2 = client.post("/api/v1/repos", json=payload)
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201, 400, 409)  # acceptable: idempotent or conflict


# --- TC-C3: List repositories ---
def test_list_repositories(client):
    client.post(
        "/api/v1/repos",
        json={"repo_url": "https://github.com/example/list-repo", "branch": "main"},
    )
    response = client.get("/api/v1/repos")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1


# --- TC-C4: Get repository by ID ---
def test_get_repository(client):
    create_r = client.post(
        "/api/v1/repos",
        json={"repo_url": "https://github.com/example/get-repo", "branch": "main"},
    )
    assert create_r.status_code in (200, 201)
    repo_id = create_r.json()["id"]

    response = client.get(f"/api/v1/repos/{repo_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo_id
    assert data["repo_url"] == "https://github.com/example/get-repo"


def test_get_repository_invalid_id_returns_404(client):
    """TC-C4: Invalid ID must return 404 not 500"""
    response = client.get("/api/v1/repos/non-existent-id-00000")
    assert response.status_code == 404
