# ML Prediction Service

Production-like educational MVP for an ML prediction service with JWT authentication,
Scikit-learn model support, asynchronous prediction execution, credit billing,
analytics dashboard, monitoring, Docker Compose, and tests.

## Current Status

The repository is being prepared stage by stage on `develop`. The current public
foundation contains the application package, configuration entry points, health
endpoint, database schema, authentication flow, base REST API contracts, quality
commands, model upload, asynchronous prediction execution, credit billing, mock
payments, and architecture documentation.

## Local Setup

Create and activate a virtual environment, then install the project with
development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the application locally:

```powershell
uvicorn app.main:app --reload
```

The health endpoint is available at:

```text
http://127.0.0.1:8000/api/v1/health
```

## Quality Checks

```powershell
ruff check .
ruff format --check .
pytest
coverage run -m pytest
coverage report
```

## Docker Compose

Build and start the local infrastructure:

```powershell
docker compose up --build
```

On Windows, if Docker fails to build from a path with non-ASCII characters,
disable BuildKit for this shell session and retry:

```powershell
$env:DOCKER_BUILDKIT="0"
$env:COMPOSE_DOCKER_CLI_BUILD="0"
docker compose up --build
```

Services:

| Service | URL / Port | Purpose |
| --- | --- | --- |
| `backend` | `http://127.0.0.1:18000` | FastAPI application |
| `dashboard` | `http://127.0.0.1:18501` | Streamlit dashboard service |
| `postgres` | `127.0.0.1:15432` | PostgreSQL database |
| `redis` | `127.0.0.1:16379` | Redis broker/result backend |
| `worker` | internal | Celery worker |

Stop services:

```powershell
docker compose down
```

## Database Migrations

Apply the current database schema:

```powershell
alembic upgrade head
```

The local Docker Compose backend also runs `alembic upgrade head` before Uvicorn
starts, so a clean compose startup prepares the database automatically.

Create future schema revisions from SQLAlchemy models:

```powershell
alembic revision --autogenerate -m "describe change"
```

The schema design is documented in `docs/database.md`.

## Authentication

The MVP auth flow is available in Swagger:

```text
http://127.0.0.1:18000/docs
```

Implemented endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/auth/register` | Register a default-role user |
| `POST /api/v1/auth/login` | Return a JWT bearer token |
| `POST /api/v1/auth/logout` | Document stateless client-side logout |
| `GET /api/v1/users/me` | Return the current authenticated user |
| `PATCH /api/v1/users/me` | Update allowed profile fields |
| `GET /api/v1/users/admin-check` | Verify admin role enforcement |

The auth design is documented in `docs/authentication.md`.

## REST API

Swagger/OpenAPI is available at:

```text
http://127.0.0.1:18000/docs
```

The base API surface is defined for system health, auth, users, models,
predictions, billing, and payments. Some workflow endpoints intentionally return
`501 not_implemented` until their implementation steps arrive.

The API contract and error format are documented in `docs/api.md`.

## ML Models

Authenticated users can upload trusted Scikit-learn/joblib/pickle model artifacts
through `POST /api/v1/models`. Uploaded artifacts are stored under
`MODEL_STORAGE_PATH`, validated for a callable `predict` method, and recorded in
the `ml_models` table.

The model upload flow is documented in `docs/ml-models.md`.

## Predictions

Authenticated users can create asynchronous prediction tasks with
`POST /api/v1/predictions`. The API returns a queued task immediately, and the
worker stores either `result_payload.predictions` or an execution error.

The prediction lifecycle is documented in `docs/predictions.md`.

## Billing

The core billing layer tracks integer credits through a user balance and an
immutable ledger. Prediction requests require available credits, and successful
predictions debit the configured prediction price. Failed predictions do not
debit credits.

The billing rules are documented in `docs/billing.md`.

## Payments

Authenticated users can create mock payments with `POST /api/v1/payments` and
confirm them with `POST /api/v1/payments/{payment_id}/confirm`. Confirmation
adds credits through the billing ledger and is safe to repeat.

The mock payment flow is documented in `docs/payments.md`.

## Project Structure

```text
.
├── src/app/                    Future FastAPI application package
│   ├── api/                    REST API routers and contracts
│   ├── auth/                   JWT auth and access control
│   ├── users/                  User domain
│   ├── ml/                     Model loading and ML services
│   ├── billing/                Credit balance and transactions
│   ├── payments/               Mock/sandbox payment flow
│   ├── dashboard/              Future Streamlit analytics dashboard
│   ├── db/                     Database sessions, models, migrations glue
│   ├── core/                   Settings, errors, shared application utilities
│   └── main.py                 Future application entry point
├── tests/                      Future unit and integration tests
├── migrations/                 Future database migrations
├── alembic.ini                 Alembic configuration
├── configs/                    Configuration templates
├── docker/                     Docker-related files
├── docker-compose.yml          Local infrastructure stack
├── Dockerfile                  Application container image
└── docs/                       Public project documentation
```

## Development Workflow

Work happens on `develop` first. Completed logical stages move to
`Waiting for Approval` after checks pass. Nothing is pushed to `origin` or merged
to `main` without explicit owner approval.
