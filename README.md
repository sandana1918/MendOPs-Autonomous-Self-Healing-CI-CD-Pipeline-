# MendOps

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

## Test

```powershell
pytest tests/test_guards.py
```

## Deploy

Use a Linux VM/VPS because the secure patch sandbox needs Docker.

See [DEPLOYMENT.md](DEPLOYMENT.md).
