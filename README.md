# ML Prediction Service

Production-like educational MVP for an ML prediction service with JWT authentication,
Scikit-learn model support, asynchronous prediction execution, credit billing,
analytics dashboard, monitoring, Docker Compose, and tests.

## Current Status

The repository is being prepared stage by stage on `develop`. The current public
foundation contains the application package, configuration entry points, health
endpoint, database schema, authentication flow, base REST API contracts, quality
commands, model upload, asynchronous prediction execution, credit billing, mock
payments, promo codes, analytics dashboard, monitoring, and architecture
documentation. The test suite has an explicit coverage gate, and the app now
fails fast on unsafe non-local security settings.

The public documentation starts at `docs/index.md`.

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
coverage report --fail-under=70
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
| `prometheus` | `http://127.0.0.1:19090` | Prometheus metrics server |
| `grafana` | `http://127.0.0.1:13000` | Grafana monitoring dashboard |
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

The schema design is documented in `docs/database.md`, with the full ERD in
`docs/erd.md`.

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

The API surface is implemented for system health, auth, users, models,
predictions, billing, payments, and promo codes.

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

## Promo Codes

Admins can create fixed-credit promo codes, and users can redeem active codes
once into their common credit balance. Successful redemption writes a
`promo_credit` billing transaction.

The promo code flow is documented in `docs/promo-codes.md`.

## Dashboard

The Streamlit dashboard is available at:

```text
http://127.0.0.1:18501
```

Authenticated users can view their balance, prediction statuses, credit ledger,
uploaded models, mock payments, and promo redemptions. The dashboard uses the
same API login flow as Swagger.

The dashboard flow is documented in `docs/dashboard.md`.

## Monitoring

The backend exposes Prometheus-compatible metrics at:

```text
http://127.0.0.1:18000/metrics
```

Prometheus is available at `http://127.0.0.1:19090`, and Grafana is available at
`http://127.0.0.1:13000` with local credentials `admin / admin`.

The monitoring setup is documented in `docs/monitoring.md`.

## Testing

The automated suite covers the main MVP flows: authentication, API contracts,
model upload, asynchronous predictions, billing, mock payments, promo codes,
analytics aggregation, monitoring metrics, and cross-user data isolation.

Coverage is configured in `pyproject.toml` with a minimum total threshold of
70%. At Testing stage completion, the local suite result is 58 passed tests and
85% total coverage.

The testing strategy is documented in `docs/testing.md`.

## Security

The application validates sensitive runtime settings on startup. Non-local
environments must disable debug mode and provide a non-placeholder JWT secret
with at least 32 characters. JWT algorithm selection is restricted to `HS256`.

Security hardening covers malformed password hashes, expired tokens, inactive
users, model upload filename sanitization, hidden storage paths, and ownership
boundaries across user data.

The security checklist and residual risks are documented in `docs/security.md`.

## Business Plan

The project uses prepaid credits as the monetization model. One successful
prediction costs `1` credit; failed predictions are not charged. Mock payments
represent balance top-ups in the MVP, and fixed-credit promo codes provide the
implemented marketing mechanic.

The short business plan is documented in `docs/business-plan.md`.

## Documentation

The main public documentation entry point is `docs/index.md`. It links the
architecture diagram, ERD, API contracts, infrastructure, security, testing, and
domain-specific guides.

## Project Structure

```text
.
├── src/app/                    FastAPI application package
│   ├── api/                    REST API routers and contracts
│   ├── auth/                   JWT auth and access control
│   ├── users/                  User domain
│   ├── ml/                     Model loading and ML services
│   ├── billing/                Credit balance and transactions
│   ├── payments/               Mock/sandbox payment flow
│   ├── promo_codes/            Fixed-credit promo codes
│   ├── dashboard/              Streamlit analytics dashboard
│   ├── monitoring/             Prometheus metrics endpoint
│   ├── db/                     Database sessions, models, migrations glue
│   ├── core/                   Settings, errors, shared application utilities
│   └── main.py                 Application entry point
├── tests/                      Unit and integration tests
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
