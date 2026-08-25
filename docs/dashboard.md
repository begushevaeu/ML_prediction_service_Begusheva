# Dashboard

Step 11 adds a Streamlit dashboard for the authenticated user.

## Scope

- The dashboard connects to the public FastAPI API.
- Users log in with the same email and password as the API.
- The dashboard does not read the database directly.
- State is held in the Streamlit browser session.
- The API base URL can be changed from the sidebar for local testing.

## Visible Data

- Current credit balance.
- Prediction counts and statuses.
- Credit ledger totals.
- Uploaded model list.
- Mock payment history.
- Promo code redemption history.

## Local URL

```text
http://127.0.0.1:18501
```

When Docker Compose starts the stack, the dashboard service talks to the backend
through the internal `http://backend:8000/api/v1` URL. When running Streamlit
outside Docker, the default API URL is `http://127.0.0.1:18000/api/v1`.

## Manual Check

1. Start the local stack.
2. Open the dashboard URL.
3. Log in as a registered user.
4. Verify that balance, predictions, billing, models, payments, and promo
   redemptions are visible in their tabs.
