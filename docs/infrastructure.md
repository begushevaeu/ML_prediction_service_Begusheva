# Infrastructure

Step 2 defines the local Docker Compose infrastructure for ML Prediction
Service. It provides service wiring only; auth, database models, ML prediction,
billing, payments, and analytics behavior are implemented in later stages.

## Services

| Service | Image / command | Responsibility |
| --- | --- | --- |
| `backend` | local `Dockerfile`, Alembic + Uvicorn | Applies migrations, then runs the FastAPI app on host port `18000` |
| `worker` | local `Dockerfile`, Celery | Starts the asynchronous worker process |
| `dashboard` | local `Dockerfile`, Streamlit | Starts the dashboard service on host port `18501` |
| `prometheus` | `prom/prometheus:v2.55.1` | Scrapes backend metrics on host port `19090` |
| `grafana` | `grafana/grafana:11.3.1` | Shows provisioned monitoring dashboards on host port `13000` |
| `postgres` | `postgres:16-alpine` | Provides PostgreSQL on host port `15432` |
| `redis` | `redis:7-alpine` | Provides Redis on host port `16379` |

## Volumes

| Volume | Purpose |
| --- | --- |
| `grafana_data` | Grafana local data directory |
| `prometheus_data` | Prometheus local time-series data |
| `postgres_data` | PostgreSQL data directory |
| `model_storage` | Local model storage path for the MVP |

## Configuration

The compose file uses environment variables aligned with `.env.example`.
Secrets in `.env.example` are placeholders and must not be reused for a real
deployment.

Published host ports can be overridden with `BACKEND_PORT`, `DASHBOARD_PORT`,
`PROMETHEUS_PORT`, `GRAFANA_PORT`, `POSTGRES_PORT`, and `REDIS_PORT`.

## Commands

```powershell
docker compose config
docker compose up --build
docker compose down
```

On Windows, Docker may fail to build from project paths containing non-ASCII
characters. If that happens, disable BuildKit for the current PowerShell session
and run compose again:

```powershell
$env:DOCKER_BUILDKIT="0"
$env:COMPOSE_DOCKER_CLI_BUILD="0"
docker compose up --build
```

## Current Health Checks

- PostgreSQL uses `pg_isready`.
- Redis uses `redis-cli ping`.
- Backend calls `GET /api/v1/health` locally.
- Dashboard depends on the healthy backend.
- Prometheus scrapes `GET /metrics` from the backend.
- Grafana uses provisioned Prometheus datasource and dashboard files.

Worker process health will become richer when real asynchronous tasks are added
in the prediction stage.
