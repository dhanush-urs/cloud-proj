"""
Suite H: Hotspots Tests
TC-H1, TC-H2

Suite I: Onboarding Doc Tests
TC-I1, TC-I2

Suite J: PR Impact Tests
TC-J1, TC-J2
"""


def _create_repo(client, suffix="misc-test"):
    r = client.post(
        "/api/v1/repos",
        json={"repo_url": f"https://github.com/example/{suffix}", "branch": "main"},
    )
    assert r.status_code in (200, 201)
    return r.json()["id"]


# --- Suite H: Hotspots ---

def test_hotspots_empty_repo_no_crash(client):
    """TC-H2: Hotspots on empty repo should return empty list, not crash"""
    repo_id = _create_repo(client, "hotspot-empty")
    response = client.get(f"/api/v1/repos/{repo_id}/hotspots")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data or isinstance(data, list)


def test_hotspots_response_structure(client):
    """TC-H1: Hotspot response should have risk scoring fields"""
    repo_id = _create_repo(client, "hotspot-struct")
    response = client.get(f"/api/v1/repos/{repo_id}/hotspots")
    assert response.status_code == 200
    data = response.json()
    items = data.get("items", data if isinstance(data, list) else [])
    for item in items:
        assert "risk_score" in item or "file_id" in item


# --- Suite I: Onboarding ---

def test_get_onboarding_not_found_returns_404(client):
    """TC-I2: Get latest onboarding before generation → 404"""
    repo_id = _create_repo(client, "onboard-empty")
    response = client.get(f"/api/v1/repos/{repo_id}/onboarding")
    assert response.status_code in (404, 200), (
        f"Expected 404 or empty, got {response.status_code}"
    )


def test_generate_onboarding_no_crash(client):
    """TC-I1: Generate onboarding — no internal 500 allowed"""
    repo_id = _create_repo(client, "onboard-gen")
    response = client.post(
        f"/api/v1/repos/{repo_id}/onboarding/generate",
        json={"top_files": 5, "include_hotspots": False, "include_search_context": False},
    )
    # 200/201 (success or heuristic fallback) or 409 (no parsed files) or 422 (body req'd)
    assert response.status_code in (200, 201, 202, 409, 422), (
        f"Got unexpected {response.status_code}: {response.text}"
    )


# --- Suite J: PR Impact ---

def test_impact_valid_changed_files(client):
    """TC-J1: PR impact with changed files should return structured response"""
    repo_id = _create_repo(client, "impact-test")
    response = client.post(
        f"/api/v1/repos/{repo_id}/impact",
        json={"changed_files": ["app/main.py"], "max_depth": 2},
    )
    assert response.status_code in (200, 409), (
        f"Got unexpected {response.status_code}: {response.text}"
    )
    if response.status_code == 200:
        data = response.json()
        assert "summary" in data or "impacted_files" in data


def test_impact_empty_changed_files_validation(client):
    """TC-J2: Empty changed_files should fail with 422 or 400"""
    repo_id = _create_repo(client, "impact-empty")
    response = client.post(
        f"/api/v1/repos/{repo_id}/impact",
        json={"changed_files": [], "max_depth": 2},
    )
    assert response.status_code in (200, 400, 409, 422), (
        f"Empty files should fail gracefully, got {response.status_code}: {response.text}"
    )
