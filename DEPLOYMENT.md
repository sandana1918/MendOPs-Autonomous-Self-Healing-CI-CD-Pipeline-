# PatchForge AI Deployment

Deploy on a Linux VM/VPS. Do not use serverless for the full version because the sandbox needs Docker.

## 1. Server

Use Ubuntu 22.04 or 24.04.

Open ports:

```text
80    webhook/API through nginx
3000  Grafana, optional
9090  Prometheus, optional
```

## 2. Install Runtime

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip nginx docker.io docker-compose-plugin
sudo systemctl enable --now docker nginx
```

## 3. Create User

```bash
sudo useradd -m -s /bin/bash patchforge
sudo usermod -aG docker patchforge
```

Log out/in or restart the service later so Docker group applies.

## 4. Clone

```bash
sudo git clone https://github.com/sandana1918/PatchForgeAI.git /opt/patchforge
sudo chown -R patchforge:patchforge /opt/patchforge
cd /opt/patchforge
```

## 5. Configure

```bash
sudo -u patchforge cp .env.production.example .env
sudo -u patchforge nano .env
```

Set:

```env
AI_API_KEY="gsk_..."
AI_BASE_URL="https://api.groq.com/openai/v1"
MODEL_NAME="llama-3.3-70b-versatile"
DEMO_PATCH_FALLBACK=false
GITHUB_WEBHOOK_SECRET="random-secret"
GITHUB_TOKEN="github_pat_..."
REPOSITORY_NAME="sandana1918/PatchForgeAI"
KEYCLOAK_ENABLED=false
```

Generate webhook secret:

```bash
openssl rand -hex 32
```

## 6. Install App

```bash
sudo -u patchforge python3 -m venv .venv
sudo -u patchforge .venv/bin/pip install -r requirements.txt
sudo docker build -t sandbox-tester:latest -f Dockerfile.sandbox .
```

## 7. Run As Service

```bash
sudo cp deploy/systemd/patchforge.service /etc/systemd/system/patchforge.service
sudo systemctl daemon-reload
sudo systemctl enable --now patchforge
sudo systemctl status patchforge
```

Check:

```bash
curl http://127.0.0.1:8000/health
```

## 8. Nginx

```bash
sudo cp deploy/nginx/patchforge.conf /etc/nginx/sites-available/patchforge
sudo ln -s /etc/nginx/sites-available/patchforge /etc/nginx/sites-enabled/patchforge
sudo nginx -t
sudo systemctl reload nginx
```

Your webhook URL:

```text
http://SERVER_IP/webhook
```

For HTTPS, add a domain and Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Then webhook:

```text
https://your-domain.com/webhook
```

## 9. Monitoring

```bash
sudo -u patchforge docker compose -f docker-compose.monitoring.yml up -d
```

Open:

```text
http://SERVER_IP:9090/targets
http://SERVER_IP:3000/d/patchforge-ai/patchforge-ai
```

## 10. GitHub Webhook

Repository:

```text
https://github.com/sandana1918/PatchForgeAI/settings/hooks
```

Payload URL:

```text
https://your-domain.com/webhook
```

Content type:

```text
application/json
```

Secret:

```text
same as GITHUB_WEBHOOK_SECRET
```

Events:

```text
Issues
```

## 11. Test Live

Create a GitHub issue:

```text
Title: Application crashes with ZeroDivisionError
Body: calculate_average_rating crashes when [] is passed. Return 0.0.
```

Expected:

```text
PatchForge creates patchforge/fix-issue-* branch
PatchForge opens a pull request
Grafana shows github resolved
```

## Commands

```bash
sudo systemctl restart patchforge
sudo journalctl -u patchforge -f
sudo docker compose -f /opt/patchforge/docker-compose.monitoring.yml ps
```

