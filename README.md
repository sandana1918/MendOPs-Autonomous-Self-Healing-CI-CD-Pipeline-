# PatchForge AI

Autonomous self-healing CI/CD pipeline and secure sandboxed bug reporter.

## Run

```powershell
cd automated-bug-reporter
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
docker build -t sandbox-tester:latest -f Dockerfile.sandbox .
uvicorn app.main:app --reload --port 8000
```

## Keycloak

Set this when a trusted gateway relays GitHub webhooks with an access token:

```powershell
KEYCLOAK_ENABLED=true
KEYCLOAK_ISSUER_URL="http://localhost:8080/realms/patchforge"
KEYCLOAK_AUDIENCE="patchforge-api"
KEYCLOAK_REQUIRED_ROLE="patchforge-ci"
```

## Offline Demo

If OpenAI quota is unavailable, keep the pipeline demo running with:

```env
DEMO_PATCH_FALLBACK=true
```

## Alternate AI Provider

Use any OpenAI-compatible chat API:

```env
AI_API_KEY="provider_key"
AI_BASE_URL="https://provider.example/v1"
MODEL_NAME="provider-model"
DEMO_PATCH_FALLBACK=false
```

Leave `AI_BASE_URL` empty for OpenAI.

## Patch Scope

Single-file default:

```env
TARGET_FILE_PATH="tests/test_target.py"
TARGET_FILE_PATHS=""
```

Multi-file context:

```env
TARGET_FILE_PATH="tests/test_target.py"
TARGET_FILE_PATHS="tests/test_target.py,app/helpers.py"
```

The AI can return multiple patched files. PatchForge validates every Python file, runs sandbox tests, then commits all returned files to the PR.

## Grafana / Prometheus

Run:

```powershell
docker compose -f docker-compose.monitoring.yml up
```

Scrape:

```yaml
scrape_configs:
  - job_name: patchforge-ai
    static_configs:
      - targets: ["host.docker.internal:8000"]
```

Metrics URL:

```text
http://127.0.0.1:8000/metrics
```

## Webhook

```powershell
$body = '{"action":"opened","issue":{"number":104,"title":"Application crashes with ZeroDivisionError","body":"calculate_average_rating crashes for []"}}'
$secret = "change-me"
$hmac = [System.Security.Cryptography.HMACSHA256]::new([Text.Encoding]::UTF8.GetBytes($secret))
$hash = ($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($body)) | ForEach-Object ToString x2) -join ''
Invoke-RestMethod http://127.0.0.1:8000/webhook -Method Post -ContentType "application/json" -Headers @{"X-Hub-Signature-256"="sha256=$hash"} -Body $body
```

## Security Guard

Every AI-generated patch is statically analyzed (AST) before it is allowed to
run. The guard blocks:

- dangerous imports (`os`, `subprocess`, `socket`, `requests`, `pickle`, `ctypes`, …)
- dynamic execution and reflection builtins (`eval`, `exec`, `compile`, `__import__`,
  `getattr`/`setattr`, `open`) whether called or merely aliased (`f = eval`)
- attribute-based sandbox escapes (`__class__`, `__bases__`, `__subclasses__`,
  `__globals__`, `__builtins__`, …)

## Sandbox Backends

`SANDBOX_BACKEND` selects how patches are test-verified:

```env
SANDBOX_BACKEND=auto   # docker when reachable, else local (default)
SANDBOX_BACKEND=docker # hardened container: no network, 256MB/0.5 vCPU, non-root
SANDBOX_BACKEND=local  # restricted subprocess: isolated interpreter, stripped env, timeout
```

The local backend lets the full pipeline run on machines without Docker; the AST
guard is the primary defense in both modes.

## Benchmark

Reproducible metrics over a seeded bug corpus, malicious payloads, and benign
patches. Runs offline (local backend, no API key):

```powershell
python benchmark/run.py          # security + pipeline oracle
python benchmark/run.py --llm    # also measure live model fix-rate (needs AI_API_KEY)
```

Results are written to `benchmark/RESULTS.md` and `benchmark/results.json`. Latest
offline run: AST guard blocked **17/17** malicious payloads (100%) with **0%**
false positives, and **10/10** seeded bugs across 9 error categories validated
end-to-end at a median **~0.6s** per patch.

## Test

```powershell
pytest
```

## Deploy

Use a Linux VM/VPS because the secure patch sandbox needs Docker.

See [DEPLOYMENT.md](DEPLOYMENT.md).
