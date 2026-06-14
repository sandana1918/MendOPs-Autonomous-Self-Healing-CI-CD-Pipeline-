import asyncio
import hashlib
import hmac
import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

from app.agent import generate_patch
from app.auth import verify_keycloak_identity
from app.config import settings
from app.github_client import commit_patch_and_open_pr
from app.guards import verify_patch
from app.sandbox import run_in_sandbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patchforge")

app = FastAPI(title="PatchForge AI", version="1.0.0")

REQUEST_COUNT = Counter(
    "patchforge_http_requests_total",
    "HTTP requests handled by PatchForge AI",
    ("method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "patchforge_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ("method", "path"),
)
PIPELINE_EVENTS = Counter(
    "patchforge_pipeline_events_total",
    "PatchForge pipeline events",
    ("stage", "result"),
)


class PipelineResult(BaseModel):
    status: str
    detail: str = ""
    branch: str = ""
    pr_url: str = ""


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(perf_counter() - start)
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook", response_model=PipelineResult)
async def webhook_endpoint(request: Request) -> PipelineResult:
    body = await request.body()
    _verify_signature(body, request.headers.get("X-Hub-Signature-256"))
    await verify_keycloak_identity(request)

    payload = await request.json()
    if payload.get("action") != "opened" or "issue" not in payload:
        PIPELINE_EVENTS.labels("webhook", "ignored").inc()
        return PipelineResult(status="ignored", detail="not an opened issue event")

    issue = payload["issue"]
    issue_number = str(issue.get("number", "0"))
    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "")

    target_path = Path(settings.TARGET_FILE_PATH)
    if not target_path.exists():
        raise HTTPException(status_code=500, detail=f"missing target file: {target_path}")

    faulty_code = target_path.read_text(encoding="utf-8")
    patch = None
    feedback = ""
    last_failure = "patch generation failed"

    for attempt in range(1, settings.MAX_PATCH_ATTEMPTS + 1):
        patch = await generate_patch(issue_title, issue_body, faulty_code, feedback=feedback)
        if not patch:
            PIPELINE_EVENTS.labels("agent", "failed").inc()
            last_failure = "patch generation failed"
            break

        guard = verify_patch(patch.patched_code)
        if not guard.ok:
            PIPELINE_EVENTS.labels("guard", "blocked").inc()
            last_failure = "; ".join(guard.errors)
            feedback = f"Attempt {attempt} failed AST guard: {last_failure}"
            patch = None
            continue

        sandbox_result = await asyncio.to_thread(run_in_sandbox, patch.patched_code, str(target_path))
        if not sandbox_result["success"]:
            PIPELINE_EVENTS.labels("sandbox", "failed").inc()
            last_failure = sandbox_result["logs"]
            feedback = f"Attempt {attempt} failed pytest sandbox: {last_failure}"
            patch = None
            continue

        break

    if not patch:
        return PipelineResult(status="failed", detail=last_failure)

    branch = f"patchforge/fix-issue-{issue_number}"
    pr_result = await commit_patch_and_open_pr(
        branch_name=branch,
        file_content=patch.patched_code,
        pr_title=issue_title,
        summary=patch.explanation,
        target_file_path=str(target_path).replace("\\", "/"),
    )
    if not pr_result.ok:
        PIPELINE_EVENTS.labels("github", "verified_no_pr").inc()
        return PipelineResult(status="verified", detail=pr_result.error, branch=branch)

    PIPELINE_EVENTS.labels("github", "resolved").inc()
    return PipelineResult(status="resolved", branch=branch, pr_url=pr_result.url)


def _verify_signature(body: bytes, signature: str | None) -> None:
    expected = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="signature authentication failure",
        )
