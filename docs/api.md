# API Contracts

Step 5 defines the base REST API surface for the MVP. Swagger/OpenAPI is
available at `/docs` when the backend is running.

## Error Format

Expected HTTP and validation errors use one envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Validation error",
    "details": []
  }
}
```

Regular HTTP errors use the status code as `code`. Deferred workflow endpoints
return `501` with `code` set to `not_implemented`.

## Implemented Contracts

| Area | Endpoint | Status |
| --- | --- | --- |
| System | `GET /api/v1/health` | Implemented |
| Auth | `POST /api/v1/auth/register` | Implemented |
| Auth | `POST /api/v1/auth/login` | Implemented |
| Auth | `POST /api/v1/auth/logout` | Implemented |
| Users | `GET /api/v1/users/me` | Implemented |
| Users | `PATCH /api/v1/users/me` | Implemented |
| Users | `GET /api/v1/users/admin-check` | Implemented |
| Models | `GET /api/v1/models` | Implemented metadata list |
| Models | `GET /api/v1/models/{model_id}` | Implemented metadata lookup |
| Models | `POST /api/v1/models` | Contract only; upload follows in Step 6 |
| Predictions | `GET /api/v1/predictions` | Implemented task list |
| Predictions | `GET /api/v1/predictions/{prediction_id}` | Implemented task lookup |
| Predictions | `POST /api/v1/predictions` | Contract only; execution follows in Step 7 |
| Billing | `GET /api/v1/billing/balance` | Implemented |
| Billing | `GET /api/v1/billing/transactions` | Implemented ledger list |
| Payments | `GET /api/v1/payments` | Implemented payment list |
| Payments | `POST /api/v1/payments` | Contract only; processing follows in Step 10 |

All model, prediction, billing, and payment endpoints are protected by bearer
authentication and only return rows owned by the current user.
