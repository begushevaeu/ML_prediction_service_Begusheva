# Dashboard

The Streamlit dashboard provides two separate role-based workspaces:

- USER Cabinet for ordinary ML-service users;
- ADMIN Panel for platform administration.

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

- USER Cabinet uses a dark left sidebar with pages `Обзор`, `Предсказания`,
  `Мои модели`, and `Баланс`.
- USER overview shows balance, prediction count, active model count, latest
  predictions, and a quick `Новое предсказание` action.
- USER predictions page supports model selection, CSV/manual input, cost
  preview, async status/result display, history, and status filtering.
- USER models page supports model upload, model list, status display, and
  selecting a model for prediction. User model deletion remains disabled because
  the user-facing delete API is not implemented.
- USER balance page shows current credits, mock top-up, promo redemption,
  payment history, promo history, and the unified credit ledger.
- ADMIN Panel uses a separate sidebar with pages `Обзор`, `Пользователи`,
  `Модели`, `Платежи`, `Транзакции`, `Промокоды`, `Настройки системы`,
  `Мониторинг`, and `Логи и ошибки`.
- ADMIN pages use `/api/v1/admin/*` endpoints for global platform data.

## User Actions

- Users can upload a Scikit-learn `.joblib`, `.pkl`, or `.pickle` model from
  the `Мои модели` page.
- Users can upload a CSV file with prediction rows or enter rows manually,
  submit the prediction from the `Предсказания` page, refresh pending tasks,
  and see the result or error in the same page.
- Users can top up credits with a one-button mock payment flow from the
  `Баланс` page.
- Users can redeem a promo code from a separate block on the `Баланс` page.
- The dashboard shows one friendly operation history for payment credits, promo
  credits, debits, and adjustments.
- Admin users enter a separate ADMIN Panel after login. User pages are not shown
  to admins.
- Admins can inspect global users, models, payments, transactions, promo codes,
  settings, monitoring summary, and prediction errors.
- Admin overview shows prediction activity as stacked daily status bars, with
  success/failure inside each column and the daily total displayed above it.
- Admins can block/unblock users through `User.is_active`.
- Admins can soft-delete problematic models while preserving prediction history.
- Admins can create and deactivate fixed-credit promo codes.
- Admins can create manual credit adjustments from the transactions page.

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
4. Verify that the USER sidebar shows `Обзор`, `Предсказания`, `Мои модели`,
   and `Баланс`.
5. Upload a model in `Мои модели`.
6. Select one uploaded model on `Предсказания`, upload a CSV file with
   prediction rows, run the prediction, and verify that the status/result
   appears.
7. Top up credits and redeem a promo code from `Баланс`.
8. Log in as an admin user and verify that the ADMIN sidebar is shown instead
   of USER pages.
9. Inspect admin overview, users, models, payments, transactions, promo codes,
   settings, monitoring, and logs.
10. Create and deactivate a fixed-credit promo code.
