# Authentication

Step 4 adds the MVP authentication and user-management flow.

## Flow

1. A user registers with `POST /api/v1/auth/register`.
2. The user logs in with `POST /api/v1/auth/login`.
3. The backend returns a JWT bearer token.
4. Protected endpoints read the bearer token from the `Authorization` header.
5. Stateless logout is handled by discarding the bearer token on the client.

The Swagger UI exposes the OAuth2 password flow through the Authorize button.
For this MVP, the OAuth2 `username` field is normally the user's email address.
The local admin account can also use the short `admin` login.

## Roles

The MVP has two roles:

- `user`
- `admin`

New registrations receive the `user` role. Admin accounts are not self-service;
they can be inserted or promoted later through an admin workflow. The
`GET /api/v1/users/admin-check` endpoint verifies that role checks return `403`
for ordinary users and allow admins.

For local development, the backend can bootstrap an admin account with the short
login `admin` and password `admin`. This is controlled by
`BOOTSTRAP_LOCAL_ADMIN=true` and is intended only for local/demo environments.

## Passwords And Tokens

Passwords are stored as PBKDF2-SHA256 hashes with per-password salts. JWT tokens
are signed with `JWT_SECRET_KEY` and expire after
`ACCESS_TOKEN_EXPIRE_MINUTES`.

For local development, `.env.example` uses a placeholder secret with a safe test
length. Real deployment settings must provide a unique random `JWT_SECRET_KEY`.
Outside local/test environments, the application fails startup if the default
secret is still in use, if debug mode is enabled, or if an unsupported JWT
algorithm is configured.
