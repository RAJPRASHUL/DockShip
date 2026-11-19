# DockShip

[![CI/CD](https://github.com/RAJPRASHUL/DockShip/actions/workflows/ci.yml/badge.svg)](https://github.com/RAJPRASHUL/DockShip/actions/workflows/ci.yml)

DockShip is a small self-hosted deployment control plane for trusted GitHub
repositories. It clones an app, builds a Docker image, runs a health gate,
and routes traffic through blue-green releases.

## Architecture

GitHub push webhook -> Nginx -> FastAPI control plane -> Docker

The control plane runs as a host process under systemd because it needs access
to the Docker socket and Nginx configuration. The CI image is a scanned,
versioned artifact in GHCR; production deployment updates the host with SSH.

## Quickstart

Requirements: Python 3.12+, Docker, Nginx, `uv`, and Git.

```powershell
uv sync
$env:DOCKSHIP_API_KEY = "local-development-key"
$env:GITHUB_WEBHOOK_SECRET = "local-webhook-secret"
uv run uvicorn dockship.main:app --reload
```

The health endpoint is public:

```text
GET http://localhost:8000/health
```

All app and deployment APIs require `X-API-Key`. The GitHub webhook uses
`X-Hub-Signature-256` instead.

## CLI

```powershell
uv run dockship login --server http://localhost:8000
uv run dockship register hello https://github.com/example/hello --branch main
uv run dockship deploy hello
uv run dockship logs hello
uv run dockship rollback hello
```

For production, use an SSH tunnel to keep the API private:

```text
ssh -N -L 8000:127.0.0.1:8000 ubuntu@<elastic-ip>
```

Only `/webhook/github` and app virtual hosts are public through Nginx.

## App contract

An application repository must contain a Dockerfile. The image must listen on
the `PORT` environment variable and return HTTP 200 from `/health`.

The example app is in [`examples/hello-app`](examples/hello-app).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Public service health |
| GET/POST | `/apps` | List or register applications |
| POST | `/apps/{name}/deploy` | Queue a deployment |
| POST | `/apps/{name}/rollback` | Queue a rollback |
| GET | `/apps/{name}/logs` | Read active container logs |
| GET | `/deployments/{id}` | Read deployment status |
| POST | `/webhook/github` | Receive signed GitHub pushes |

## AWS deployment

Create a budget before provisioning. Run `infra/bootstrap.sh` once, replace
the Terraform backend bucket in `infra/main.tf`, then:

```bash
cd infra
terraform init
terraform plan -var='key_name=<ec2-key-pair>'
terraform apply -var='key_name=<ec2-key-pair>'
```

Destroy temporary environments to avoid ongoing AWS charges:

```bash
terraform destroy -var='key_name=<ec2-key-pair>'
```

Destroying and recreating the instance changes the Elastic IP and therefore
requires updating the GitHub webhook URL.

## Metrics, backups, and security

Metrics and the management API are private and should be reached through the
SSH tunnel. The `/metrics` endpoint exposes deployment counters, deployment
duration, and the active-app gauge.

The instance role can back up SQLite without keys on disk:

```bash
/opt/dockship/deploy/scripts/backup.sh <backup-bucket>
aws s3 cp s3://<backup-bucket>/backups/2026-01-01.db /tmp/restore.db
sqlite3 /var/lib/dockship/dockship.db ".restore /tmp/restore.db"
```

Test a restore before relying on backups. Schedule the backup script at 02:00
and run `deploy/scripts/cleanup.sh` weekly after confirming rollback images
are retained. Deploy only trusted repositories: Dockerfiles execute on the
deployment host. SSH is key-only, the webhook is rate-limited, containers
have CPU/memory/log limits, and the instance uses IMDSv2.
