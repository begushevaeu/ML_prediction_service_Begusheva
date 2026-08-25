# Payments

Step 9 adds the MVP mock payment flow for topping up credits.

## Rules

- Payments are owned by the authenticated user.
- `POST /api/v1/payments` creates a `pending` mock payment.
- `POST /api/v1/payments/{payment_id}/confirm` marks the payment as
  `succeeded`.
- Successful confirmation creates one `payment_credit` billing transaction.
- Repeated confirmation is idempotent and does not credit the balance twice.
- Users can list and inspect only their own payments.

## Create Payment

```json
{
  "credits_purchased": 10,
  "amount_cents": 500,
  "currency": "USD"
}
```

The MVP does not use a credit package catalog yet. The request directly stores
the number of purchased credits and the mock amount paid in minor currency
units.

## Confirm Payment

```text
POST /api/v1/payments/{payment_id}/confirm
```

Confirmation is the local sandbox equivalent of a successful provider callback.
It updates the payment status and credits the user's balance in one transaction.
