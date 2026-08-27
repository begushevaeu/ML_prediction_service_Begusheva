# UI Architecture

This document describes the implemented Streamlit UI architecture for separate
USER and ADMIN workspaces. The dashboard still follows the project rule that UI
code talks to FastAPI only and does not read PostgreSQL directly.

## Role Routing

Authentication uses the existing JWT flow:

1. Dashboard logs in through `POST /api/v1/auth/login`.
2. Dashboard loads the current account through `GET /api/v1/users/me`.
3. If `role == "user"`, the USER Cabinet is rendered.
4. If `role == "admin"`, the ADMIN Panel is rendered.
5. Logout clears the bearer token from Streamlit session state.

The requested role names `USER` and `ADMIN` map to the backend role values
`user` and `admin`.

## Design System

Both roles share one Streamlit design system:

- dark left sidebar;
- light main content area;
- compact dashboard composition;
- rounded KPI cards and bordered work areas;
- purple primary actions;
- green/orange/red status badges;
- role-specific navigation and page sets.

USER pages never show admin controls. ADMIN pages do not reuse customer
self-service workflows.

## USER Cabinet

Sidebar pages:

| Page | Data and actions | API |
| --- | --- | --- |
| Обзор | Balance KPI, prediction count, active model count, latest predictions, quick `Новое предсказание` action | `GET /billing/balance`, `GET /predictions`, `GET /models` |
| Предсказания | Model selection, CSV/manual rows, cost preview, async launch, polling, result/error, status-filtered history | `GET /models`, `POST /predictions`, `GET /predictions`, `GET /predictions/{id}` |
| Мои модели | Upload model, list owned models, model status, select model for prediction | `POST /models`, `GET /models` |
| Баланс | Current credits, mock top-up, promo activation, payment history, promo history, operation history | `GET /billing/balance`, `POST /payments`, `POST /payments/{id}/confirm`, `GET /payments`, `POST /promo-codes/redeem`, `GET /promo-codes/redemptions`, `GET /billing/transactions` |

### USER Notes

- User model deletion is visible only as a disabled action because there is no
  user-facing `DELETE /api/v1/models/{model_id}` endpoint.
- Prediction cost preview uses the current MVP rule: `1` credit per successful
  prediction.
- Exact per-prediction cost is inferred for USER history because the
  user-facing prediction response does not include `cost_credits`.
- Backend prediction statuses are `queued`, `running`, `succeeded`, and
  `failed`; UI labels map them to friendly Russian labels and colored badges.

## ADMIN Panel

Admin endpoints live under `/api/v1/admin/*` and are protected by
`require_roles("admin")`.

Sidebar pages:

| Page | Data and actions | API |
| --- | --- | --- |
| Обзор | Global users, predictions, success rate, credits, activity chart, derived activity feed | `GET /admin/dashboard/summary`, `GET /admin/dashboard/activity`, `GET /admin/events` |
| Пользователи | Global user list, role, balance, active status, detail counts, block/unblock | `GET /admin/users`, `GET /admin/users/{id}`, `PATCH /admin/users/{id}/status` |
| Модели | Global model list, owner, upload date, status, run count, soft-delete | `GET /admin/models`, `GET /admin/models/{id}`, `DELETE /admin/models/{id}` |
| Платежи | Global mock payment history, amount, credits, date, status | `GET /admin/payments`, `GET /admin/payments/{id}` |
| Транзакции | Global credit ledger, type filter, manual admin adjustment | `GET /admin/billing/transactions`, `POST /billing/adjustments` |
| Промокоды | Fixed-credit create/list/deactivate and promo-code information table | `GET /promo-codes`, `POST /promo-codes`, `PATCH /promo-codes/{id}/deactivate` |
| Настройки системы | Read-only non-secret runtime settings | `GET /admin/system/settings` |
| Мониторинг | Compact service summary, disk summary, Prometheus/Grafana links | `GET /admin/monitoring/summary` |
| Логи и ошибки | Failed prediction errors with related user/prediction/model | `GET /admin/logs` |

### ADMIN Notes

- User block/unblock updates `User.is_active`; inactive users cannot authenticate.
- Admin self-deactivation is blocked.
- Model deletion is implemented as soft-delete: `MLModel.status` becomes
  `deleted`, the stored artifact is removed when possible, and new prediction
  requests only accept models with status `uploaded`.
- Existing prediction history is preserved after model soft-delete.
- Promo codes remain fixed-credit only. Discount promo codes still require
  database and API support.
- Settings are read-only because current configuration is environment-backed.
- Monitoring intentionally stays a summary plus Prometheus/Grafana links, not a
  duplicate monitoring system.
- Logs are derived from failed prediction tasks. A broader persisted
  `system_events` or `audit_events` model remains future work.

## Data Models Used

| Model | UI usage |
| --- | --- |
| `User` | role routing, user list, active status |
| `Role` | role labels |
| `CreditBalance` | user balance and admin user balance |
| `MLModel` | user model list and admin global model list |
| `PredictionTask` | prediction histories, status/result/error, admin logs |
| `Payment` | user/admin payment history |
| `BillingTransaction` | user/admin credit ledger and prediction cost |
| `PromoCode` | admin promo management |
| `PromoRedemption` | user promo history and admin promo usage |

## Remaining Gaps

| Gap | Reason |
| --- | --- |
| User-owned model deletion | No user-facing delete endpoint yet |
| Public pricing endpoint | UI currently uses the documented MVP default of `1` credit |
| Discount promo codes | Current database and API support fixed credits only |
| Editable system settings | Settings are environment-backed, not database-backed |
| Full CPU/RAM/Celery monitoring | Should remain in Prometheus/Grafana unless a structured summary is explicitly required |
| Persistent system/audit logs | Current admin logs derive only from failed prediction tasks |
