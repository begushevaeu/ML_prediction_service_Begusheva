# Dashboard

Step 11 adds a Streamlit dashboard for the authenticated user.

## Scope

- The dashboard connects to the public FastAPI API.
- Users log in with the same email or login and password as the API.
- The dashboard does not read the database directly.
- State is held in the Streamlit browser session.
- The API base URL can be changed from the sidebar for local testing.

## Local Admin Login

For local development, the application dashboard admin uses the same credentials
as Grafana:

```text
login: admin
password: admin
```

## Visible Data

- Prediction panel above the user tabs for selecting one uploaded model,
  uploading prediction data, and running a prediction.
- Uploaded model list in the model upload tab.
- Prediction history with friendly statuses.
- Unified balance operation history.

## User Actions

- Users can upload a Scikit-learn `.joblib`, `.pkl`, or `.pickle` model from
  the `Загрузить новую модель` tab.
- Users can upload a CSV file with prediction rows or enter rows manually,
  submit the prediction from the panel above the user tabs, refresh pending
  tasks, and see the result or error in the same panel.
- Users can top up credits with a one-button mock payment flow from the
  `Пополнить баланс` tab.
- Users can redeem a promo code from a separate block in the same
  `Пополнить баланс` tab.
- The user tabs are `Загрузить новую модель`, `История предсказаний`,
  `Пополнить баланс`, and `История операций`.
- The dashboard shows one friendly operation history for payment credits, promo
  credits, debits, and adjustments.
- Admin users enter a separate admin mode after login.
- Admin mode does not show user metrics or user tabs.
- Admin mode can create fixed-credit promo codes with mandatory credit amount,
  total activation limit, start date, and expiration date.
- Admin mode can deactivate existing promo codes without deleting redemption
  history.
- Admin mode shows a single promo code list at the top with status, credit
  amount, total activation limit, total usage, issued credits, and dates.

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
4. Verify that the user tabs are `Загрузить новую модель`,
   `История предсказаний`, `Пополнить баланс`, and `История операций`.
5. Upload a model in the `Загрузить новую модель` tab.
6. Select one uploaded model in the prediction panel above the tabs, upload a
   CSV file with prediction rows, run the prediction, and verify that the
   prediction status/result appears.
7. Log in as an admin user and verify that only the admin promo code screen is
   visible.
8. Create a promo code with credit amount, total activation limit, start date,
   and expiration date.
9. Deactivate the promo code and verify it is no longer redeemable.
