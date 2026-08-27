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
Customer-facing top-ups are handled by the mock Payments flow.

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

## Payment Credits

Successful mock payment confirmation creates one `payment_credit` transaction
linked to the payment row. Repeated confirmation reuses the same idempotency key
and does not increase the balance twice.

## Promo Credits

Successful promo code redemption creates one `promo_credit` transaction linked
to the redemption row. A user can redeem the same promo code only once, and the
overall redemption limit is checked before credits are granted.
