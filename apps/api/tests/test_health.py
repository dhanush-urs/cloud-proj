def test_health(client):
    """TC-C1: Health endpoints"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "repobrain-api"


def test_health_live(client):
    """TC-C1: Liveness probe"""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_health_ready(client):
    """TC-C1: Readiness check — DB must be ok"""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["database"]["ok"] is True


def test_health_ready_has_version(client):
    """TC-N1: Readiness still returns structured JSON even when degraded"""
    response = client.get("/api/v1/health/ready")
    data = response.json()
    assert "version" in data
    assert "service" in data
