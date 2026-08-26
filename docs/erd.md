# Entity Relationship Diagram

This ERD documents the implemented MVP database schema.

## Diagram

```mermaid
erDiagram
  roles ||--o{ users : assigns
  users ||--|| credit_balances : owns
  users ||--o{ ml_models : uploads
  users ||--o{ prediction_tasks : requests
  users ||--o{ payments : creates
  users ||--o{ promo_redemptions : redeems
  users ||--o{ billing_transactions : owns
  credit_balances ||--o{ billing_transactions : records
  ml_models ||--o{ prediction_tasks : serves
  prediction_tasks ||--o{ billing_transactions : may_bill
  payments ||--o{ billing_transactions : credits
  promo_codes ||--o{ promo_redemptions : grants
  promo_redemptions ||--o{ billing_transactions : credits

  roles {
    int id PK
    string name UK
    string description
    datetime created_at
    datetime updated_at
  }

  users {
    int id PK
    string email UK
    string password_hash
    string full_name
    bool is_active
    int role_id FK
    datetime created_at
    datetime updated_at
  }

  credit_balances {
    int id PK
    int user_id FK
    int credits_available
    datetime created_at
    datetime updated_at
  }

  ml_models {
    int id PK
    int owner_id FK
    string name
    string storage_path
    string framework
    string status
    json model_metadata
    datetime created_at
    datetime updated_at
  }

  prediction_tasks {
    int id PK
    int user_id FK
    int model_id FK
    string celery_task_id UK
    string status
    json input_payload
    json result_payload
    text error_message
    datetime started_at
    datetime completed_at
    datetime created_at
    datetime updated_at
  }

  payments {
    int id PK
    int user_id FK
    string provider
    string provider_payment_id UK
    string status
    int credits_purchased
    int amount_cents
    string currency
    datetime created_at
    datetime updated_at
  }

  promo_codes {
    int id PK
    string code UK
    int credit_amount
    int max_redemptions
    int redemptions_count
    bool is_active
    datetime starts_at
    datetime expires_at
    int created_by_user_id FK
    datetime created_at
    datetime updated_at
  }

  promo_redemptions {
    int id PK
    int user_id FK
    int promo_code_id FK
    int credits_granted
    datetime created_at
    datetime updated_at
  }

  billing_transactions {
    int id PK
    int user_id FK
    int balance_id FK
    int prediction_task_id FK
    int payment_id FK
    int promo_redemption_id FK
    string transaction_type
    string direction
    int amount_credits
    int balance_after_credits
    string status
    string description
    string idempotency_key UK
    datetime created_at
    datetime updated_at
  }
```

## Table Ownership

| Table | Primary owner |
| --- | --- |
| `roles` | System |
| `users` | Auth/user domain |
| `credit_balances` | Billing domain |
| `ml_models` | ML domain, owned by a user |
| `prediction_tasks` | Prediction domain, owned by a user |
| `payments` | Payments domain, owned by a user |
| `promo_codes` | Promo domain, admin-managed |
| `promo_redemptions` | Promo domain, owned by a user |
| `billing_transactions` | Billing ledger, owned by a user and linked to source operations |

## Key Constraints

- `users.email` is unique.
- `roles.name` is unique.
- `credit_balances.user_id` is unique, enforcing one common balance per user.
- `payments.provider_payment_id` is unique.
- `prediction_tasks.celery_task_id` is unique when present.
- `promo_codes.code` is unique.
- `promo_redemptions` has a unique `(user_id, promo_code_id)` pair.
- `billing_transactions.idempotency_key` is unique when present.
- Credit amounts are positive, and resulting balances cannot be negative.

## Ledger Links

`billing_transactions` can point to the source operation that caused the balance
change:

| Transaction type | Direction | Source link |
| --- | --- | --- |
| `payment_credit` | `credit` | `payment_id` |
| `promo_credit` | `credit` | `promo_redemption_id` |
| `prediction_debit` | `debit` | `prediction_task_id` |
| `adjustment` | `credit` or `debit` | admin operation |

This keeps the user's current balance fast to read while preserving an auditable
history of balance changes.
