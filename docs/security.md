# Security

Step 14 reviews and hardens the main MVP security boundaries.

## Runtime Settings

`app.main:create_app` validates security-sensitive settings before the FastAPI
application is created.

Non-local environments must:

- use a `JWT_SECRET_KEY` different from the repository placeholder;
- use a JWT secret with at least 32 characters;
- keep `APP_DEBUG=false`.

All environments must:

- use the supported JWT algorithm `HS256`;
- keep access token lifetime, model upload size, and prediction price positive.

This prevents a production-like deployment from accidentally starting with local
placeholder secrets or debug responses.

## Authentication

- Passwords are stored as salted PBKDF2-SHA256 hashes.
- Malformed stored password hashes are rejected safely instead of raising an
  internal error during login checks.
- JWT tokens are signed, expire after `ACCESS_TOKEN_EXPIRE_MINUTES`, and must
  include a subject.
- Expired tokens, invalid tokens, inactive users, and users without a role are
  rejected with `401`.
- Admin-only endpoints rely on role checks and return `403` for regular users.

## Ownership Boundaries

User-facing endpoints scope data by the authenticated user:

- models;
- prediction tasks;
- billing transactions;
- payments;
- promo code redemptions.

Security tests verify that a second user cannot list or fetch another user's
records across these domains.

## Model Uploads

The MVP accepts trusted Scikit-learn/joblib/pickle model artifacts. These file
formats can execute code while being loaded, so this is suitable for trusted
educational uploads only.

Current guardrails:

- only `.joblib`, `.pkl`, and `.pickle` extensions are accepted;
- upload size is limited by `MAX_MODEL_UPLOAD_SIZE_BYTES`;
- stored filenames are generated server-side;
- original filenames are sanitized before metadata is returned;
- internal storage paths are not returned by public API responses;
- invalid artifacts are removed from storage.

Production hardening would require sandboxed model loading/execution or a safer
model format.

## Billing And Payments

Credit balance changes go through ledger service functions with idempotency
keys. Payment confirmation and promo redemption use stable idempotency keys so
repeated calls do not create duplicate credits.

PostgreSQL row locks are requested for balance/payment/promo updates. SQLite
test databases do not fully emulate row-level locking, so tests focus on
idempotency and ownership behavior. Real concurrent billing checks should run
against PostgreSQL before a production deployment.

## Monitoring

The local `/metrics` endpoint is unauthenticated so Prometheus can scrape it in
Docker Compose. In a real deployment, it should be exposed only on a private
network or protected by infrastructure-level access controls.

## Residual Risks

- No request rate limiting is implemented yet.
- No account lockout or login throttling is implemented yet.
- Mock payments are educational and do not validate a real payment provider
  signature.
- Pickle/joblib model artifacts remain trusted-input only.
- Docker Compose secrets are local placeholders and must not be reused outside
  local development.
