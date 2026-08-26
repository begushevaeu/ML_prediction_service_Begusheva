# Testing

Step 13 formalizes the automated test coverage requirement for the MVP.

## Coverage Gate

The project requires total test coverage above 70%. This threshold is configured
in `pyproject.toml`:

```toml
[tool.coverage.report]
fail_under = 70
```

The local verification command is:

```powershell
coverage run -m pytest
coverage report --fail-under=70
```

## Current Result

At Testing stage completion, the local suite result is:

```text
58 passed, 8 warnings
TOTAL coverage: 85%
```

The warnings come from third-party test/runtime dependencies and do not indicate
application test failures.

## Covered Areas

- Authentication registration, login, protected resources, profile update, and
  role checks.
- Versioned API contracts, health checks, validation errors, and unified error
  envelopes.
- Database schema constraints and important indexes.
- Scikit-learn model upload, metadata storage, extension checks, invalid file
  handling, and size validation.
- Asynchronous prediction creation, worker success, worker failure, result
  storage, and billing behavior for failed predictions.
- Credit balance reads, ledger history, manual admin adjustments, insufficient
  balance handling, and idempotent credit/debit operations.
- Mock payment creation, confirmation, repeated confirmation, and owner scoping.
- Promo code creation, activation limits, repeated redemption prevention, and
  promo credit ledger writes.
- Analytics dashboard aggregation helpers.
- Prometheus metrics output and business metric collection.
- Cross-user isolation for models, predictions, billing transactions, payments,
  promo redemptions, and detail endpoints.

## Acceptance Notes

The Testing stage adds a cross-cutting acceptance test file that checks the
highest-risk seams across already implemented modules:

- Validation and missing-route responses use the same error envelope shape.
- A second user cannot see or fetch another user's domain data.
- Billing idempotency keys prevent duplicate credit/debit ledger rows.
