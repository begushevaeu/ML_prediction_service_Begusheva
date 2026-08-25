# ML Prediction Service

Production-like educational MVP for an ML prediction service with JWT authentication,
Scikit-learn model support, asynchronous prediction execution, credit billing,
analytics dashboard, monitoring, Docker Compose, and tests.

## Current Status

The repository is being prepared stage by stage on `develop`. The current public
foundation contains the application package, configuration entry points, health
endpoint, quality commands, and initial architecture documentation.

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
├── configs/                    Configuration templates
├── docker/                     Docker-related files
└── docs/                       Public project documentation
```

## Development Workflow

Work happens on `develop` first. Completed logical stages move to
`Waiting for Approval` after checks pass. Nothing is pushed to `origin` or merged
to `main` without explicit owner approval.
