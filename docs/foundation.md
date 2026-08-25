# Foundation

Step 1 defines the public foundation of ML Prediction Service. It intentionally
does not implement auth, ML, billing, payments, or dashboard business behavior.

## Application Boundaries

The application package is located in `src/app`.

| Package | Responsibility |
| --- | --- |
| `app.api` | REST API routers and contracts |
| `app.auth` | JWT authentication and access control |
| `app.users` | User domain |
| `app.ml` | Scikit-learn model management and prediction helpers |
| `app.billing` | Credit balance and transaction logic |
| `app.payments` | Mock/sandbox payment flow |
| `app.dashboard` | Future Streamlit analytics dashboard |
| `app.db` | Database sessions, models, and migration integration |
| `app.core` | Settings, errors, and shared application utilities |

## Runtime Configuration

Foundation settings are loaded from environment variables in `app.core.config`.
The current settings are deliberately small:

- `APP_NAME`
- `APP_ENV`
- `APP_DEBUG`
- `API_V1_PREFIX`

Secrets and infrastructure URLs are represented in `.env.example` and will be
connected to real implementation stages later.

## Application Entry Point

`app.main:create_app` creates the FastAPI application. The module-level
`app.main:app` object is the ASGI entry point used by Uvicorn.

Current endpoints:

- `GET /` returns service metadata.
- `GET /api/v1/health` returns a minimal readiness signal.

## Quality Pipeline

The local quality commands are:

```powershell
ruff check .
ruff format --check .
pytest
coverage run -m pytest
coverage report
```

GitHub Actions runs the same foundation checks on pushes and pull requests to
`develop` and `main`.
