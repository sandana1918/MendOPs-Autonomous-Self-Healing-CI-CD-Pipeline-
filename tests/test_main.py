import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import app.main as main_module
from app.agent import PatchResponse
from app.config import settings
from app.github_client import PullRequestResult
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


def test_webhook_retries_guard_failure_then_opens_pr(monkeypatch):
    calls = []

    async def fake_generate_patch(issue_title, issue_body, faulty_code, feedback=""):
        calls.append(feedback)
        if len(calls) == 1:
            return PatchResponse(explanation="bad", patched_code="import os\n")
        return PatchResponse(
            explanation="fixed",
            patched_code=(
                "def calculate_average_rating(ratings_list):\n"
                "    if not ratings_list:\n"
                "        return 0.0\n"
                "    return sum(ratings_list) / len(ratings_list)\n"
            ),
        )

    async def fake_commit_patch_and_open_pr(**kwargs):
        return PullRequestResult(True, url="https://example.test/pr/1")

    monkeypatch.setattr(main_module, "generate_patch", fake_generate_patch)
    monkeypatch.setattr(main_module, "run_in_sandbox", lambda code, path: {"success": True, "logs": "ok"})
    monkeypatch.setattr(main_module, "commit_patch_and_open_pr", fake_commit_patch_and_open_pr)

    body = json.dumps(
        {
            "action": "opened",
            "issue": {
                "number": 42,
                "title": "Application crashes with ZeroDivisionError",
                "body": "calculate_average_rating crashes for []",
            },
        },
        separators=(",", ":"),
    )
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signature(body.encode("utf-8")),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "resolved",
        "detail": "",
        "branch": "patchforge/fix-issue-42",
        "pr_url": "https://example.test/pr/1",
    }
    assert len(calls) == 2
    assert calls[1].startswith("Attempt 1 failed AST guard")


def _signature(body: bytes) -> str:
    digest = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
