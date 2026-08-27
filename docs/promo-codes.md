# Promo Codes

Step 10 adds fixed-credit promo codes as the MVP marketing mechanic.

## Rules

- Admins create promo codes with a fixed credit amount and required total
  activation limit.
- User-entered codes are normalized to uppercase.
- Users redeem codes with `POST /api/v1/promo-codes/redeem`.
- A user can redeem the same promo code only once; this per-user limit is fixed
  and is not configurable per promo code.
- Start date and expiration date are required for new promo codes.
- Active status, start date, expiration date, and total activation limits are
  enforced.
- Successful redemption creates one `promo_credit` billing transaction.
- Admins can deactivate promo codes without deleting redemption history.

## Admin Create

```json
{
  "code": "WELCOME10",
  "credit_amount": 10,
  "max_redemptions": 100,
  "is_active": true,
  "starts_at": "2026-08-27T00:00:00Z",
  "expires_at": "2026-09-27T23:59:00Z"
}
```

`max_redemptions`, `starts_at`, and `expires_at` are required.
Listing, creation, and deactivation are admin-only.

## Admin Deactivate

```http
PATCH /api/v1/promo-codes/{promo_code_id}/deactivate
Authorization: Bearer <admin-token>
```

The response returns the promo code with `is_active: false`. Existing redemption
history remains available for analytics.

## User Redeem

```json
{
  "code": "WELCOME10"
}
```

The response includes the granted credits and resulting balance after the promo
credit transaction is posted.
