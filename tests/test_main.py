from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_rejects_missing_signature():
    response = client.post("/webhook", json={"action": "opened", "issue": {}})
    assert response.status_code == 403


def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "patchforge_http_requests_total" in response.text
