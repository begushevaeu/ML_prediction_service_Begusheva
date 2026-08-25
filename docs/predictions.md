# Predictions

Step 7 adds asynchronous prediction execution.

## Flow

1. A user uploads a trusted model with `POST /api/v1/models`.
2. The user creates a prediction task with `POST /api/v1/predictions`.
3. The API validates ownership and the input payload, stores a `queued` task,
   enqueues Celery execution, and returns the task ID immediately.
4. The worker loads the stored model artifact and calls `predict`.
5. The task becomes `succeeded` with a result payload or `failed` with an error.
6. The user checks status and result with `GET /api/v1/predictions/{id}`.

## Input Contract

The MVP prediction payload is:

```json
{
  "model_id": 1,
  "input_payload": {
    "rows": [[1, 2, 3]]
  }
}
```

`rows` must be a non-empty list. It is passed directly to the model's
`predict(rows)` method.

## Statuses

| Status | Meaning |
| --- | --- |
| `queued` | API accepted the request and enqueued worker execution |
| `running` | Worker started model execution |
| `succeeded` | Worker saved predictions in `result_payload.predictions` |
| `failed` | Worker saved an execution error in `error_message` |

## Billing

Credit reservation and debit are intentionally deferred to the billing stage.
This step focuses on the prediction lifecycle and worker execution.
