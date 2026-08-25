# Promo Codes

Step 10 adds fixed-credit promo codes as the MVP marketing mechanic.

## Rules

- Admins create promo codes with a fixed credit amount.
- User-entered codes are normalized to uppercase.
- Users redeem codes with `POST /api/v1/promo-codes/redeem`.
- A user can redeem the same promo code only once.
- Active, start date, expiration date, and max redemption limits are enforced.
- Successful redemption creates one `promo_credit` billing transaction.

## Admin Create

```json
{
  "code": "WELCOME10",
  "credit_amount": 10,
  "max_redemptions": 100,
  "is_active": true
}
```

`max_redemptions`, `starts_at`, and `expires_at` are optional. Listing and
creation are admin-only.

## User Redeem

```json
{
  "code": "WELCOME10"
}
```

The response includes the granted credits and resulting balance after the promo
credit transaction is posted.
