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
return `501` with `code` set to `not_implemented`. ML upload validation can also
return `unsupported_model_file`, `invalid_model_file`, or `model_file_too_large`.

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
| Models | `POST /api/v1/models` | Implemented multipart model upload |
| Predictions | `GET /api/v1/predictions` | Implemented task list |
| Predictions | `GET /api/v1/predictions/{prediction_id}` | Implemented task lookup |
| Predictions | `POST /api/v1/predictions` | Implemented async task creation |
| Billing | `GET /api/v1/billing/balance` | Implemented |
| Billing | `GET /api/v1/billing/transactions` | Implemented ledger list |
| Payments | `GET /api/v1/payments` | Implemented payment list |
| Payments | `POST /api/v1/payments` | Contract only; processing follows in Step 10 |

All model, prediction, billing, and payment endpoints are protected by bearer
authentication and only return rows owned by the current user.

## Model Upload

`POST /api/v1/models` accepts a multipart form:

| Field | Required | Purpose |
| --- | --- | --- |
| `name` | yes | User-visible model name |
| `file` | yes | `.joblib`, `.pkl`, or `.pickle` model artifact |
| `framework` | no | Defaults to `scikit-learn` |
| `metadata_json` | no | JSON object with user-supplied metadata |

The MVP validates trusted Scikit-learn/joblib/pickle artifacts by loading the
file and checking that the resulting object has a callable `predict` method.
Prediction execution is still deferred to Step 7.

## Prediction Execution

`POST /api/v1/predictions` accepts `model_id` and `input_payload.rows`, stores a
queued task, and returns immediately with the prediction task ID. A Celery worker
loads the model, calls `predict(rows)`, and stores either
`result_payload.predictions` or `error_message`.
