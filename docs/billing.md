# Billing

Step 8 adds the core credit balance and ledger behavior.

## Rules

- New users start with `0` credits.
- The default prediction price is `1` credit.
- A prediction request requires enough available credits before it is queued.
- A successful prediction creates a `prediction_debit` transaction.
- A failed prediction does not debit credits.
- Billing changes write immutable `billing_transactions` rows.
- Idempotency keys prevent repeated credit/debit operations from changing the
  balance twice.

## Manual Adjustments

Admins can create manual adjustments with:

```text
POST /api/v1/billing/adjustments
```

The endpoint supports both `credit` and `debit` directions. It is intended as
the simplest internal operation for local MVP testing and future support tasks.
Customer-facing top-ups are deferred to the Payments step.

## Prediction Billing

`POST /api/v1/predictions` checks the user's current balance before creating a
task. The worker debits credits only after the model finishes successfully.

If a user has no credits, the API returns `402` with:

```json
{
  "error": {
    "code": "insufficient_credits",
    "message": "Insufficient credits: 0 available, 1 required",
    "details": {
      "available": 0,
      "required": 1
    }
  }
}
```
