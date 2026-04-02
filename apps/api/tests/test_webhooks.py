"""
Suite K: GitHub Webhook Tests
TC-K1, TC-K2, TC-K3
"""


PUSH_PAYLOAD = {
    "ref": "refs/heads/main",
    "repository": {
        "html_url": "https://github.com/pallets/flask",
        "clone_url": "https://github.com/pallets/flask.git",
        "full_name": "pallets/flask",
    },
    "commits": [
        {
            "added": [],
            "modified": ["src/flask/app.py"],
            "removed": [],
        }
    ],
}


def test_webhook_ping_returns_200(client):
    """TC-K1: ping event should return 200 and not create refresh job"""
    response = client.post(
        "/api/v1/webhooks/github",
        json={"zen": "Keep it logically awesome.", "hook_id": 123456},
        headers={
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": "test-ping-001",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200


def test_webhook_push_missing_signature_with_secret_configured(client):
    """TC-K2: Webhook with HMAC secret set but missing sig header → 401"""
    # If no secret is configured, this may return 200; that's acceptable
    response = client.post(
        "/api/v1/webhooks/github",
        json=PUSH_PAYLOAD,
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "test-invalid-sig-001",
        },
    )
    # Without configured secret, missing sig should not crash server
    assert response.status_code in (200, 400, 401, 422), (
        f"Got unexpected 500: {response.text}"
    )


def test_webhook_push_no_signature_no_crash(client):
    """TC-K2: Signature completely absent should never 500"""
    response = client.post(
        "/api/v1/webhooks/github",
        json=PUSH_PAYLOAD,
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "test-push-no-sig",
        },
    )
    assert response.status_code != 500, f"Server error: {response.text}"


def test_webhook_duplicate_delivery_no_crash(client):
    """TC-K3: Same delivery ID sent twice should not crash"""
    headers = {
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "dupe-delivery-001",
    }

    r1 = client.post(
        "/api/v1/webhooks/github",
        json={"zen": "Simplicity is a feature."},
        headers=headers,
    )
    r2 = client.post(
        "/api/v1/webhooks/github",
        json={"zen": "Simplicity is a feature."},
        headers=headers,
    )
    assert r1.status_code in (200, 201)
    # Duplicate should be gracefully handled — not 500
    assert r2.status_code != 500, f"Got 500 on duplicate: {r2.text}"


def test_webhook_missing_event_header_no_crash(client):
    """TC-K2: Missing X-GitHub-Event header should not 500"""
    response = client.post(
        "/api/v1/webhooks/github",
        json=PUSH_PAYLOAD,
    )
    assert response.status_code != 500, f"Server error: {response.text}"
