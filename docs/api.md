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
can use `501` with `code` set to `not_implemented`. The currently implemented
MVP surface does not expose deferred workflow endpoints. ML upload validation
can return `unsupported_model_file`, `invalid_model_file`, or
`model_file_too_large`. Billing can return `insufficient_credits`.
Promo codes can return `promo_code_exists`, `promo_not_active`,
`promo_already_redeemed`, or `promo_limit_reached`.

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
| Billing | `POST /api/v1/billing/adjustments` | Implemented admin adjustment |
| Payments | `GET /api/v1/payments` | Implemented payment list |
| Payments | `GET /api/v1/payments/{payment_id}` | Implemented payment lookup |
| Payments | `POST /api/v1/payments` | Implemented mock payment creation |
| Payments | `POST /api/v1/payments/{payment_id}/confirm` | Implemented mock confirmation |
| Promo Codes | `GET /api/v1/promo-codes` | Implemented admin list |
| Promo Codes | `POST /api/v1/promo-codes` | Implemented admin create |
| Promo Codes | `GET /api/v1/promo-codes/redemptions` | Implemented user redemption list |
| Promo Codes | `POST /api/v1/promo-codes/redeem` | Implemented user redemption |

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
Prediction execution runs asynchronously through the worker.

## Prediction Execution

`POST /api/v1/predictions` accepts `model_id` and `input_payload.rows`, stores a
queued task, and returns immediately with the prediction task ID. A Celery worker
loads the model, calls `predict(rows)`, and stores either
`result_payload.predictions` or `error_message`.

Prediction creation requires enough credits. Successful predictions debit the
configured prediction price, while failed predictions do not debit credits.

## Payments

`POST /api/v1/payments` creates a pending mock payment. `POST
/api/v1/payments/{payment_id}/confirm` marks it as succeeded and adds the
purchased credits to the user's balance through a `payment_credit` ledger row.
Repeated confirmation is safe and does not credit the balance twice.

## Promo Codes

Admins can create fixed-credit promo codes. Users redeem a code once with
`POST /api/v1/promo-codes/redeem`, which creates a `promo_credit` ledger row and
adds credits to the common balance. Inactive, expired, exhausted, missing, and
already-redeemed codes are rejected.

## Example Flow

Register a user:

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "owner@example.com",
  "password": "strong-password",
  "full_name": "Project Owner"
}
```

Log in through the OAuth2 password form and use the returned bearer token:

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=owner@example.com&password=strong-password
```

Create a mock payment and confirm it:

```http
POST /api/v1/payments
Authorization: Bearer <token>
Content-Type: application/json

{
  "credits_purchased": 10,
  "amount_cents": 500,
  "currency": "USD"
}
```

```http
POST /api/v1/payments/{payment_id}/confirm
Authorization: Bearer <token>
```

Create a prediction after uploading a trusted model:

```http
POST /api/v1/predictions
Authorization: Bearer <token>
Content-Type: application/json

{
  "model_id": 1,
  "input_payload": {
    "rows": [[1, 2, 3]]
  }
}
```

Check prediction status:

```http
GET /api/v1/predictions/{prediction_id}
Authorization: Bearer <token>
```
