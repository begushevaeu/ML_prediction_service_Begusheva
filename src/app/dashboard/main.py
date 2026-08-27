"""Streamlit analytics dashboard entry point."""

from __future__ import annotations

import csv
import json
import mimetypes
import os
from datetime import UTC, date, datetime, time, timedelta
from html import escape
from io import StringIO
from time import monotonic, sleep
from typing import Any
from urllib import error, parse, request
from uuid import uuid4

import streamlit as st

from app import APP_NAME
from app.dashboard.service import build_dashboard_metrics

DEFAULT_API_BASE_URL = "http://127.0.0.1:18000/api/v1"
MOCK_CENTS_PER_CREDIT = 50
PREDICTION_PRICE_CREDITS = 1
USER_PAGES = ["Обзор", "Предсказания", "Мои модели", "Баланс"]
ADMIN_PAGES = [
    "Обзор",
    "Пользователи",
    "Модели",
    "Платежи",
    "Транзакции",
    "Промокоды",
    "Настройки системы",
    "Мониторинг",
    "Логи и ошибки",
]
COLUMN_LABELS = {
    "id": "ID",
    "model_id": "ID модели",
    "status": "Статус",
    "result_payload": "Результат",
    "error_message": "Ошибка",
    "created_at": "Создано",
    "transaction_type": "Тип",
    "direction": "Направление",
    "amount_credits": "Кредиты",
    "balance_after_credits": "Баланс после",
    "name": "Название",
    "framework": "Фреймворк",
    "credits_purchased": "Кредиты",
    "amount_cents": "Сумма, центы",
    "currency": "Валюта",
    "code": "Код",
    "credit_amount": "Кредиты",
    "max_redemptions": "Лимит",
    "redemptions_count": "Активации",
    "is_active": "Активен",
    "credits_granted": "Начислено",
    "starts_at": "Начало",
    "expires_at": "Окончание",
    "updated_at": "Обновлено",
}
TRANSACTION_TYPE_LABELS = {
    "payment_credit": "Пополнение баланса",
    "promo_credit": "Промокод",
    "prediction_debit": "Списание за prediction",
    "adjustment": "Корректировка баланса",
}
TRANSACTION_STATUS_LABELS = {
    "posted": "Готово",
    "pending": "В обработке",
    "voided": "Отменено",
}
PREDICTION_STATUS_LABELS = {
    "queued": "В очереди",
    "running": "Выполняется",
    "succeeded": "Готово",
    "failed": "Ошибка",
}
MODEL_STATUS_LABELS = {
    "uploaded": "Загружена",
    "active": "Активна",
    "inactive": "Заблокирован",
    "deleted": "Удалена",
    "failed": "Ошибка",
}
PENDING_PREDICTION_STATUSES = {"queued", "running"}
SUCCESS_PREDICTION_STATUSES = {"succeeded"}
FAILED_PREDICTION_STATUSES = {"failed"}
PredictionCell = int | float | str
PredictionRows = list[list[PredictionCell]]


class DashboardApiError(RuntimeError):
    """Raised when the dashboard API request fails."""


def _inject_dashboard_styles(*, hide_sidebar: bool = False) -> None:
    styles = """
        :root {
            --ml-purple: #7c3aed;
            --ml-purple-dark: #5b21b6;
            --ml-sidebar: #111827;
            --ml-text: #111827;
            --ml-muted: #6b7280;
            --ml-border: #e5e7eb;
            --ml-surface: #ffffff;
            --ml-app-bg: #0f172a;
            --ml-page-text: #f8fafc;
            --ml-page-muted: #cbd5e1;
            --ml-green-bg: #dcfce7;
            --ml-green-text: #166534;
            --ml-orange-bg: #ffedd5;
            --ml-orange-text: #9a3412;
            --ml-red-bg: #fee2e2;
            --ml-red-text: #991b1b;
            --ml-gray-bg: #f3f4f6;
            --ml-gray-text: #374151;
        }
        .stApp,
        [data-testid="stAppViewContainer"] {
            background: var(--ml-app-bg);
            color: var(--ml-page-text);
        }
        .main .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        section[data-testid="stSidebar"] {
            background: var(--ml-sidebar);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div {
            color: #e5e7eb;
        }
        section[data-testid="stSidebar"] input {
            color: #111827;
        }
        .ml-sidebar-brand {
            font-size: 1rem;
            font-weight: 800;
            color: #ffffff;
            margin: 0.25rem 0 1rem 0;
        }
        .ml-sidebar-nav-label {
            color: #9ca3af;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0;
            margin: 1rem 0 0.4rem 0;
            text-transform: uppercase;
        }
        .ml-sidebar-footer {
            margin-top: 2rem;
            padding: 0.85rem;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            color: #e5e7eb;
            word-break: break-word;
        }
        .ml-login-heading {
            margin: 0 auto 1rem auto;
            max-width: 520px;
            text-align: center;
        }
        .ml-login-heading h1 {
            color: var(--ml-page-text);
            font-size: 2rem;
            line-height: 1.15;
            margin: 0;
        }
        .ml-login-heading p {
            color: var(--ml-page-muted);
            margin: 0.45rem 0 0 0;
        }
        .ml-page-kicker {
            color: var(--ml-purple);
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 0.1rem;
        }
        .ml-page-title {
            color: var(--ml-page-text);
            font-size: 2rem;
            line-height: 1.15;
            font-weight: 850;
            margin: 0;
        }
        .ml-page-subtitle {
            color: var(--ml-page-muted);
            margin: 0.35rem 0 1.25rem 0;
        }
        .ml-status {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.18rem 0.56rem;
            font-size: 0.78rem;
            line-height: 1.2;
            font-weight: 750;
            white-space: nowrap;
        }
        .ml-status-success {
            color: var(--ml-green-text);
            background: var(--ml-green-bg);
        }
        .ml-status-pending {
            color: var(--ml-orange-text);
            background: var(--ml-orange-bg);
        }
        .ml-status-failed {
            color: var(--ml-red-text);
            background: var(--ml-red-bg);
        }
        .ml-status-muted {
            color: var(--ml-gray-text);
            background: var(--ml-gray-bg);
        }
        .ml-note {
            color: var(--ml-page-muted);
            font-size: 0.9rem;
        }
        .ml-metric-card {
            background: #ffffff;
            border: 1px solid var(--ml-border);
            border-radius: 8px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
            min-height: 112px;
            padding: 1rem;
        }
        .ml-metric-label {
            color: #374151 !important;
            -webkit-text-fill-color: #374151 !important;
            font-size: 0.82rem;
            font-weight: 800;
            margin-bottom: 0.4rem;
        }
        .ml-metric-value {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            font-size: 1.75rem;
            font-weight: 850;
            line-height: 1.1;
        }
        .ml-metric-caption {
            color: #4b5563 !important;
            -webkit-text-fill-color: #4b5563 !important;
            font-size: 0.88rem;
            margin-top: 0.45rem;
        }
        .ml-activity-summary {
            background: #ffffff;
            border: 1px solid var(--ml-border);
            border-radius: 8px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
            min-height: 260px;
            padding: 1rem;
        }
        .ml-activity-summary,
        .ml-activity-summary * {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        .ml-activity-title {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            font-size: 0.95rem;
            font-weight: 850;
            margin-bottom: 0.2rem;
        }
        .ml-activity-subtitle {
            color: #6b7280 !important;
            -webkit-text-fill-color: #6b7280 !important;
            font-size: 0.82rem;
            margin-bottom: 1rem;
        }
        .ml-activity-row {
            margin-top: 0.85rem;
        }
        .ml-activity-row-head {
            align-items: center;
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            font-size: 0.84rem;
            font-weight: 750;
        }
        .ml-activity-track {
            background: #eef2f7;
            border-radius: 999px;
            height: 0.5rem;
            margin-top: 0.35rem;
            overflow: hidden;
        }
        .ml-activity-fill {
            border-radius: 999px;
            height: 100%;
        }
        .ml-activity-success {
            background: #22c55e;
        }
        .ml-activity-failed {
            background: #ef4444;
        }
        .ml-activity-other {
            background: #f59e0b;
        }
        div[data-testid="stMetric"] {
            background: var(--ml-surface);
            border: 1px solid var(--ml-border);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }
        main div[data-testid="stMetric"] *,
        main div[data-testid="stMetric"] label,
        main div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
        }
        main div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {
            color: var(--ml-muted) !important;
            -webkit-text-fill-color: var(--ml-muted) !important;
        }
        main div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--ml-surface);
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
            border-color: var(--ml-border);
            border-radius: 8px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
        }
        main div[data-testid="stVerticalBlockBorderWrapper"] *:not(.ml-status) {
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
        }
        main div[data-testid="stVerticalBlockBorderWrapper"] .ml-status-success {
            color: var(--ml-green-text) !important;
            -webkit-text-fill-color: var(--ml-green-text) !important;
        }
        main div[data-testid="stVerticalBlockBorderWrapper"] .ml-status-pending {
            color: var(--ml-orange-text) !important;
            -webkit-text-fill-color: var(--ml-orange-text) !important;
        }
        main div[data-testid="stVerticalBlockBorderWrapper"] .ml-status-failed {
            color: var(--ml-red-text) !important;
            -webkit-text-fill-color: var(--ml-red-text) !important;
        }
        main div[data-testid="stVerticalBlockBorderWrapper"] .ml-status-muted {
            color: var(--ml-gray-text) !important;
            -webkit-text-fill-color: var(--ml-gray-text) !important;
        }
        main div[data-testid="stExpander"],
        main div[data-testid="stAlert"],
        main div[data-testid="stDataFrame"],
        main div[data-testid="stTable"] {
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
        }
        main div[data-testid="stExpander"] *:not(svg):not(path),
        main div[data-testid="stAlert"] *:not(svg):not(path),
        main div[data-testid="stDataFrame"] *:not(svg):not(path),
        main div[data-testid="stTable"] *:not(svg):not(path) {
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
        }
        main div[style*="background-color: rgb(255, 255, 255)"],
        main div[style*="background-color: rgb(255, 255, 255)"] *:not(svg):not(path),
        main div[style*="background: rgb(255, 255, 255)"],
        main div[style*="background: rgb(255, 255, 255)"] *:not(svg):not(path),
        main div[style*="background-color: white"],
        main div[style*="background-color: white"] *:not(svg):not(path) {
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
        }
        main label,
        main .stTextInput label,
        main .stTextArea label,
        main .stNumberInput label,
        main .stDateInput label,
        main .stTimeInput label {
            color: var(--ml-text) !important;
            font-weight: 700;
        }
        main input,
        main textarea,
        main [data-baseweb="input"] input,
        main [data-baseweb="textarea"] textarea {
            background: #ffffff !important;
            color: var(--ml-text) !important;
            -webkit-text-fill-color: var(--ml-text) !important;
            caret-color: var(--ml-purple) !important;
        }
        main input::placeholder,
        main textarea::placeholder {
            color: #6b7280 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #6b7280 !important;
        }
        main [data-baseweb="select"],
        main [data-baseweb="select"] * {
            color: var(--ml-text) !important;
        }
        section[data-testid="stSidebar"] .stButton > button {
            justify-content: flex-start;
            min-height: 2.55rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.04);
            color: #f9fafb;
            font-weight: 700;
            text-align: left;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            border-color: rgba(255, 255, 255, 0.24);
            background: rgba(124, 58, 237, 0.22);
            color: #ffffff;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: var(--ml-purple);
            border-color: var(--ml-purple);
            color: #ffffff;
        }
        .stButton > button[kind="primary"] {
            background: var(--ml-purple);
            border-color: var(--ml-purple);
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .stButton > button[kind="primary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: var(--ml-purple-dark);
            border-color: var(--ml-purple-dark);
        }
    """
    if hide_sidebar:
        styles += """
        section[data-testid="stSidebar"],
        div[data-testid="stSidebarCollapsedControl"],
        button[title="Open sidebar"],
        button[title="Close sidebar"] {
            display: none !important;
            visibility: hidden !important;
        }
        .main .block-container {
            max-width: 620px;
            padding-top: 12vh;
        }
        """

    st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)


def _render_page_title(title: str, subtitle: str, *, kicker: str = "USER Cabinet") -> None:
    st.markdown(f'<div class="ml-page-kicker">{escape(kicker)}</div>', unsafe_allow_html=True)
    st.markdown(f'<h1 class="ml-page-title">{escape(title)}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="ml-page-subtitle">{escape(subtitle)}</p>', unsafe_allow_html=True)


def _render_metric_card(label: str, value: Any, caption: str | None = None) -> None:
    caption_html = ""
    if caption:
        caption_html = f'<div class="ml-metric-caption">{escape(caption)}</div>'

    st.markdown(
        (
            '<div class="ml-metric-card">'
            f'<div class="ml-metric-label">{escape(label)}</div>'
            f'<div class="ml-metric-value">{escape(str(value))}</div>'
            f"{caption_html}</div>"
        ),
        unsafe_allow_html=True,
    )


def _navigate_user(page: str, *, selected_model_id: int | None = None) -> None:
    st.session_state["user_page"] = page
    if selected_model_id is not None:
        st.session_state["selected_prediction_model_id"] = selected_model_id
    st.rerun()


def _prediction_status_class(status: Any) -> str:
    normalized_status = str(status or "")
    if normalized_status in SUCCESS_PREDICTION_STATUSES | {"uploaded", "active"}:
        return "ml-status-success"
    if normalized_status in PENDING_PREDICTION_STATUSES | {"pending", "processing"}:
        return "ml-status-pending"
    if normalized_status in FAILED_PREDICTION_STATUSES | {"deleted", "error"}:
        return "ml-status-failed"
    return "ml-status-muted"


def _status_label(status: Any) -> str:
    normalized_status = str(status or "")
    if normalized_status in PREDICTION_STATUS_LABELS:
        return PREDICTION_STATUS_LABELS[normalized_status]
    if normalized_status in MODEL_STATUS_LABELS:
        return MODEL_STATUS_LABELS[normalized_status]
    return normalized_status or "-"


def _status_badge_html(status: Any) -> str:
    return (
        f'<span class="ml-status {_prediction_status_class(status)}">'
        f"{escape(_status_label(status))}</span>"
    )


def _friendly_api_error(exc: DashboardApiError) -> str:
    try:
        payload = json.loads(str(exc))
    except json.JSONDecodeError:
        return str(exc)

    error_payload = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_payload, dict):
        return str(exc)

    message = error_payload.get("message")
    if isinstance(message, str) and message:
        return message

    code = error_payload.get("code")
    return str(code or exc)


def _api_base_url() -> str:
    return str(
        st.session_state.get("api_base_url") or os.getenv("API_BASE_URL") or DEFAULT_API_BASE_URL,
    )


def _read_api_response(api_request: request.Request) -> dict[str, Any]:
    try:
        with request.urlopen(api_request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8")
        raise DashboardApiError(details or exc.reason) from exc
    except error.URLError as exc:
        raise DashboardApiError(str(exc.reason)) from exc

    if not response_body:
        return {}

    return dict(json.loads(response_body))


def _request_json(
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    form_payload: dict[str, str] | None = None,
) -> dict[str, Any]:
    url = f"{_api_base_url().rstrip('/')}/{path.lstrip('/')}"
    headers = {"Accept": "application/json"}
    body: bytes | None = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if form_payload is not None:
        body = parse.urlencode(form_payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    api_request = request.Request(url, data=body, headers=headers, method=method)
    return _read_api_response(api_request)


def _encode_multipart_form(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[str, bytes]:
    boundary = f"----ml-dashboard-{uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ],
        )

    for name, (filename, content, content_type) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                content,
                b"\r\n",
            ],
        )

    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


def _request_multipart(
    path: str,
    *,
    token: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict[str, Any]:
    url = f"{_api_base_url().rstrip('/')}/{path.lstrip('/')}"
    boundary, body = _encode_multipart_form(fields, files)
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    api_request = request.Request(url, data=body, headers=headers, method="POST")
    return _read_api_response(api_request)


def _list_items(path: str, token: str) -> list[dict[str, Any]]:
    payload = _request_json(path, token=token)
    items = payload.get("items", [])
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _login(email: str, password: str) -> str:
    payload = _request_json(
        "/auth/login",
        method="POST",
        form_payload={"username": email, "password": password},
    )
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise DashboardApiError("Access token is missing")
    return token


def _redeem_promo_code(token: str, code: str) -> dict[str, Any]:
    return _request_json(
        "/promo-codes/redeem",
        method="POST",
        token=token,
        payload={"code": code},
    )


def _create_payment(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(
        "/payments",
        method="POST",
        token=token,
        payload=payload,
    )


def _confirm_payment(token: str, payment_id: int) -> dict[str, Any]:
    return _request_json(
        f"/payments/{payment_id}/confirm",
        method="POST",
        token=token,
    )


def _create_prediction(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(
        "/predictions",
        method="POST",
        token=token,
        payload=payload,
    )


def _get_prediction(token: str, prediction_id: int) -> dict[str, Any]:
    return _request_json(f"/predictions/{prediction_id}", token=token)


def _upload_model(
    token: str,
    *,
    name: str,
    description: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> dict[str, Any]:
    return _request_multipart(
        "/models",
        token=token,
        fields=_build_model_upload_fields(name=name, description=description),
        files={"file": (filename, content, content_type)},
    )


def _create_promo_code(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(
        "/promo-codes",
        method="POST",
        token=token,
        payload=payload,
    )


def _deactivate_promo_code(token: str, promo_code_id: int) -> dict[str, Any]:
    return _request_json(
        f"/promo-codes/{promo_code_id}/deactivate",
        method="PATCH",
        token=token,
    )


def _load_admin_summary(token: str) -> dict[str, Any]:
    return _request_json("/admin/dashboard/summary", token=token)


def _load_admin_activity(token: str, period: str) -> dict[str, Any]:
    return _request_json(f"/admin/dashboard/activity?period={parse.quote(period)}", token=token)


def _load_admin_events(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/events", token)


def _load_admin_users(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/users", token)


def _load_admin_user(token: str, user_id: int) -> dict[str, Any]:
    return _request_json(f"/admin/users/{user_id}", token=token)


def _update_admin_user_status(token: str, user_id: int, is_active: bool) -> dict[str, Any]:
    return _request_json(
        f"/admin/users/{user_id}/status",
        method="PATCH",
        token=token,
        payload={"is_active": is_active},
    )


def _load_admin_models(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/models", token)


def _delete_admin_model(token: str, model_id: int) -> dict[str, Any]:
    return _request_json(f"/admin/models/{model_id}", method="DELETE", token=token)


def _load_admin_predictions(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/predictions", token)


def _load_admin_payments(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/payments", token)


def _load_admin_transactions(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/billing/transactions", token)


def _create_billing_adjustment(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(
        "/billing/adjustments",
        method="POST",
        token=token,
        payload=payload,
    )


def _load_admin_promo_redemptions(token: str, promo_code_id: int) -> list[dict[str, Any]]:
    return _list_items(f"/admin/promo-codes/{promo_code_id}/redemptions", token)


def _load_admin_settings(token: str) -> dict[str, Any]:
    return _request_json("/admin/system/settings", token=token)


def _load_admin_monitoring(token: str) -> dict[str, Any]:
    return _request_json("/admin/monitoring/summary", token=token)


def _load_admin_logs(token: str) -> list[dict[str, Any]]:
    return _list_items("/admin/logs", token)


def _load_current_user(token: str) -> dict[str, Any]:
    return _request_json("/users/me", token=token)


def _load_dashboard_data(token: str, user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user": user,
        "balance": _request_json("/billing/balance", token=token),
        "transactions": _list_items("/billing/transactions", token),
        "payments": _list_items("/payments", token),
        "predictions": _list_items("/predictions", token),
        "models": _list_items("/models", token),
        "redemptions": _list_items("/promo-codes/redemptions", token),
    }


def _format_rows(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    return [{COLUMN_LABELS.get(field, field): row.get(field) for field in fields} for row in rows]


def _is_admin(data: dict[str, Any]) -> bool:
    user = data.get("user")
    return isinstance(user, dict) and _is_admin_user(user)


def _is_admin_user(user: dict[str, Any]) -> bool:
    return user.get("role") == "admin"


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _positive_int(value: Any) -> int | None:
    amount = _as_int(value, default=0)
    if amount <= 0:
        return None
    return amount


def _parse_prediction_cell(value: str) -> PredictionCell:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Заполните все значения в строках данных.")

    try:
        return int(normalized)
    except ValueError:
        try:
            return float(normalized)
        except ValueError:
            return normalized


def _parse_prediction_rows(raw_rows: str) -> PredictionRows:
    rows: PredictionRows = []
    for raw_line in raw_rows.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        separator = ";" if ";" in line and "," not in line else ","
        rows.append([_parse_prediction_cell(cell) for cell in line.split(separator)])

    if not rows:
        raise ValueError("Добавьте хотя бы одну строку данных для prediction.")

    return rows


def _detect_csv_dialect(text: str) -> csv.Dialect:
    sample = text[:2048]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        return csv.excel


def _parse_prediction_csv(content: bytes, *, has_header: bool = False) -> PredictionRows:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV должен быть сохранен в кодировке UTF-8.") from exc

    rows: PredictionRows = []
    reader = csv.reader(StringIO(text), dialect=_detect_csv_dialect(text))
    for index, raw_row in enumerate(reader):
        if has_header and index == 0:
            continue

        cleaned_row = [cell.strip() for cell in raw_row]
        if not any(cleaned_row):
            continue
        rows.append([_parse_prediction_cell(cell) for cell in cleaned_row])

    if not rows:
        raise ValueError("CSV должен содержать хотя бы одну строку данных для prediction.")

    return rows


def _build_prediction_payload_from_rows(model_id: int, rows: PredictionRows) -> dict[str, Any]:
    resolved_model_id = _positive_int(model_id)
    if resolved_model_id is None:
        raise ValueError("Выберите модель для prediction.")
    if not rows:
        raise ValueError("Добавьте хотя бы одну строку данных для prediction.")

    return {
        "model_id": resolved_model_id,
        "input_payload": {"rows": rows},
    }


def _build_prediction_payload(model_id: int, raw_rows: str) -> dict[str, Any]:
    return _build_prediction_payload_from_rows(model_id, _parse_prediction_rows(raw_rows))


def _build_model_upload_fields(*, name: str, description: str) -> dict[str, str]:
    fields = {
        "name": name.strip(),
        "framework": "scikit-learn",
    }
    normalized_description = description.strip()
    if normalized_description:
        fields["metadata_json"] = json.dumps(
            {"description": normalized_description},
            ensure_ascii=False,
        )
    return fields


def _mime_type_for_upload(filename: str, explicit_content_type: str | None) -> str:
    if explicit_content_type:
        return explicit_content_type

    guessed_content_type = mimetypes.guess_type(filename)[0]
    return guessed_content_type or "application/octet-stream"


def _prediction_status_label(status: Any) -> str:
    normalized_status = str(status or "")
    return PREDICTION_STATUS_LABELS.get(normalized_status, normalized_status or "-")


def _wait_for_prediction_result(
    token: str,
    prediction_id: int,
    *,
    timeout_seconds: float = 8.0,
    interval_seconds: float = 1.0,
) -> dict[str, Any]:
    deadline = monotonic() + timeout_seconds
    latest = _get_prediction(token, prediction_id)

    while str(latest.get("status") or "") in PENDING_PREDICTION_STATUSES and monotonic() < deadline:
        sleep(interval_seconds)
        latest = _get_prediction(token, prediction_id)

    return latest


def _parse_api_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _promo_code_status(
    promo_code: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    if not bool(promo_code.get("is_active")):
        return "Отключен"

    current_time = now or datetime.now(UTC)
    starts_at = _parse_api_datetime(promo_code.get("starts_at"))
    expires_at = _parse_api_datetime(promo_code.get("expires_at"))
    if starts_at is not None and starts_at > current_time:
        return "Запланирован"
    if expires_at is not None and expires_at <= current_time:
        return "Истек"

    max_redemptions = promo_code.get("max_redemptions")
    if max_redemptions is not None:
        redemptions_count = _as_int(promo_code.get("redemptions_count"))
        if redemptions_count >= _as_int(max_redemptions):
            return "Лимит исчерпан"

    return "Активен"


def _promo_code_credits_issued(promo_code: dict[str, Any]) -> int:
    return _as_int(promo_code.get("credit_amount")) * _as_int(
        promo_code.get("redemptions_count"),
    )


def _format_api_datetime(value: Any) -> str:
    parsed = _parse_api_datetime(value)
    if parsed is None:
        return "-"
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_admin_promo_rows(promo_codes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ID": promo_code.get("id"),
            "Код": promo_code.get("code"),
            "Статус": _promo_code_status(promo_code),
            "Кредиты": promo_code.get("credit_amount"),
            "Использовано всего": promo_code.get("redemptions_count"),
            "Выдано кредитов": _promo_code_credits_issued(promo_code),
            "Общий лимит": str(promo_code.get("max_redemptions") or "Не задан"),
            "Дата начала": _format_api_datetime(promo_code.get("starts_at")),
            "Дата окончания": _format_api_datetime(promo_code.get("expires_at")),
        }
        for promo_code in promo_codes
    ]


def _combine_datetime(selected_date: date, selected_time: time) -> str:
    return datetime.combine(selected_date, selected_time, tzinfo=UTC).isoformat()


def _build_promo_code_payload(
    *,
    code: str,
    credit_amount: int,
    max_redemptions: int,
    starts_at: str,
    expires_at: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code.strip().upper(),
        "credit_amount": credit_amount,
        "is_active": True,
        "starts_at": starts_at,
        "expires_at": expires_at,
        "max_redemptions": max_redemptions,
    }
    return payload


def _build_payment_payload(credits_purchased: int) -> dict[str, Any]:
    return {
        "credits_purchased": credits_purchased,
        "amount_cents": credits_purchased * MOCK_CENTS_PER_CREDIT,
        "currency": "USD",
    }


def _format_credit_delta(transaction: dict[str, Any]) -> str:
    amount = _as_int(transaction.get("amount_credits"))
    prefix = "-" if transaction.get("direction") == "debit" else "+"
    return f"{prefix}{amount}"


def _format_user_operation_rows(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for transaction in transactions:
        transaction_type = str(transaction.get("transaction_type") or "")
        status = str(transaction.get("status") or "")
        rows.append(
            {
                "Дата": _format_api_datetime(transaction.get("created_at")),
                "Операция": TRANSACTION_TYPE_LABELS.get(transaction_type, transaction_type or "-"),
                "Изменение": _format_credit_delta(transaction),
                "Баланс после": transaction.get("balance_after_credits"),
                "Статус": TRANSACTION_STATUS_LABELS.get(status, status or "-"),
            },
        )
    return rows


def _format_json_preview(value: Any) -> str:
    if value in (None, "", {}, []):
        return "-"
    return json.dumps(value, ensure_ascii=False)


def _format_prediction_rows(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Дата": _format_api_datetime(prediction.get("created_at")),
            "ID": prediction.get("id"),
            "Модель": prediction.get("model_id"),
            "Статус": _prediction_status_label(prediction.get("status")),
            "Результат": _format_json_preview(prediction.get("result_payload")),
            "Ошибка": prediction.get("error_message") or "-",
        }
        for prediction in predictions
    ]


def _model_name_by_id(models: list[dict[str, Any]]) -> dict[int, str]:
    names: dict[int, str] = {}
    for model in models:
        model_id = _positive_int(model.get("id"))
        if model_id is not None:
            names[model_id] = str(model.get("name") or f"Модель #{model_id}")
    return names


def _prediction_model_name(prediction: dict[str, Any], model_names: dict[int, str]) -> str:
    model_id = _positive_int(prediction.get("model_id"))
    if model_id is None:
        return "-"
    return model_names.get(model_id, f"Модель #{model_id}")


def _prediction_cost_label(prediction: dict[str, Any]) -> str:
    status = str(prediction.get("status") or "")
    if status == "succeeded":
        return str(PREDICTION_PRICE_CREDITS)
    if status == "failed":
        return "0"
    return "-"


def _active_models_total(models: list[dict[str, Any]]) -> int:
    return len([model for model in models if str(model.get("status") or "") == "uploaded"])


def _filter_predictions_by_status(
    predictions: list[dict[str, Any]],
    filter_label: str,
) -> list[dict[str, Any]]:
    if filter_label == "Успешные":
        allowed = SUCCESS_PREDICTION_STATUSES
    elif filter_label == "В обработке":
        allowed = PENDING_PREDICTION_STATUSES
    elif filter_label == "Ошибки":
        allowed = FAILED_PREDICTION_STATUSES
    else:
        return predictions

    return [item for item in predictions if str(item.get("status") or "") in allowed]


def _payment_status_label(status: Any) -> str:
    normalized_status = str(status or "")
    labels = {
        "succeeded": "Успешно",
        "pending": "Ожидается",
        "failed": "Ошибка",
    }
    return labels.get(normalized_status, normalized_status or "-")


def _format_amount_cents(value: Any, currency: Any) -> str:
    amount = _as_int(value)
    return f"{amount / 100:.2f} {str(currency or 'USD').upper()}"


def _render_prediction_stage(status: Any) -> None:
    normalized_status = str(status or "")
    completed_created = normalized_status in {"queued", "running", "succeeded", "failed"}
    completed_running = normalized_status in {"running", "succeeded", "failed"}
    completed_result = normalized_status in {"succeeded", "failed"}

    stages = [
        ("Создано", completed_created),
        ("В обработке", completed_running),
        ("Результат", completed_result),
    ]
    columns = st.columns(3)
    for column, (label, is_done) in zip(columns, stages, strict=True):
        column.markdown(
            (
                f'<span class="ml-status '
                f'{"ml-status-success" if is_done else "ml-status-muted"}">'
                f"{escape(label)}</span>"
            ),
            unsafe_allow_html=True,
        )


def _render_prediction_table(
    predictions: list[dict[str, Any]],
    *,
    models: list[dict[str, Any]],
    token: str | None = None,
    limit: int | None = None,
    show_actions: bool = False,
) -> None:
    visible_predictions = predictions[:limit] if limit is not None else predictions
    if not visible_predictions:
        st.info("Пока нет prediction-задач.")
        return

    model_names = _model_name_by_id(models)
    columns = st.columns([1.0, 2.1, 1.5, 1.3, 1.0, 1.15] if show_actions else [2.2, 1.7, 1.3, 1])
    headers = ["ID", "Модель", "Дата", "Статус", "Стоимость", "Действие"]
    if not show_actions:
        headers = ["Модель", "Дата", "Статус", "Стоимость"]
    for column, header in zip(columns, headers, strict=True):
        column.caption(header)

    for prediction in visible_predictions:
        prediction_id = prediction.get("id")
        date_label = _format_api_datetime(prediction.get("created_at"))
        status_html = _status_badge_html(prediction.get("status"))
        cost_label = _prediction_cost_label(prediction)
        model_label = _prediction_model_name(prediction, model_names)

        columns = st.columns(
            [1.0, 2.1, 1.5, 1.3, 1.0, 1.15] if show_actions else [2.2, 1.7, 1.3, 1],
        )
        if show_actions:
            columns[0].write(prediction_id)
            columns[1].write(model_label)
            columns[2].write(date_label)
            columns[3].markdown(status_html, unsafe_allow_html=True)
            columns[4].write(cost_label)
            if columns[5].button(
                "Открыть",
                key=f"prediction-open-{prediction_id}",
                width="stretch",
            ):
                if token and _positive_int(prediction_id) is not None:
                    try:
                        st.session_state["prediction_history_detail"] = _get_prediction(
                            token,
                            _as_int(prediction_id),
                        )
                    except DashboardApiError as exc:
                        st.error(f"Не удалось открыть prediction: {_friendly_api_error(exc)}")
                        return
                else:
                    st.session_state["prediction_history_detail"] = prediction
                st.rerun()
        else:
            columns[0].write(model_label)
            columns[1].write(date_label)
            columns[2].markdown(status_html, unsafe_allow_html=True)
            columns[3].write(cost_label)


def _render_prediction_history_detail(token: str) -> None:
    detail = st.session_state.get("prediction_history_detail")
    if not isinstance(detail, dict):
        return

    prediction_id = _positive_int(detail.get("id"))
    with st.container(border=True):
        st.subheader(f"Prediction #{prediction_id or '-'}")
        _render_prediction_stage(detail.get("status"))
        st.markdown(_status_badge_html(detail.get("status")), unsafe_allow_html=True)

        result_payload = detail.get("result_payload")
        error_message = detail.get("error_message")
        if result_payload:
            st.json(result_payload)
        elif error_message:
            st.error(str(error_message))
        else:
            st.info("Результат ещё не готов.")

        actions = st.columns(2)
        if prediction_id is not None and actions[0].button("Обновить", width="stretch"):
            try:
                st.session_state["prediction_history_detail"] = _get_prediction(
                    token,
                    prediction_id,
                )
            except DashboardApiError as exc:
                st.error(f"Не удалось обновить prediction: {_friendly_api_error(exc)}")
            else:
                st.rerun()
        if actions[1].button("Закрыть", width="stretch"):
            st.session_state.pop("prediction_history_detail", None)
            st.rerun()


def _render_login() -> None:
    st.markdown(
        """
        <div class="ml-login-heading">
            <h1>ML Prediction Service</h1>
            <p>Войдите в аккаунт, чтобы открыть личный кабинет или админ-панель.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.subheader("Вход")
        with st.expander("Настройки подключения"):
            st.session_state["api_base_url"] = st.text_input(
                "API адрес",
                value=_api_base_url(),
            )
        email = st.text_input("Email или логин")
        password = st.text_input("Пароль", type="password")

        if st.button("Войти", type="primary", width="stretch"):
            try:
                st.session_state["access_token"] = _login(email, password)
                st.session_state["login_error"] = ""
            except DashboardApiError as exc:
                st.session_state["login_error"] = str(exc)
            else:
                st.rerun()

    if st.session_state.get("login_error"):
        st.error("Не удалось войти. Проверьте email, пароль и API адрес.")


def _render_authenticated_sidebar(user: dict[str, Any], *, is_admin: bool = False) -> str:
    st.sidebar.markdown(
        '<div class="ml-sidebar-brand">ML Prediction Service</div>',
        unsafe_allow_html=True,
    )
    role_label = "ADMIN Panel" if is_admin else "USER Cabinet"
    st.sidebar.caption(role_label)

    pages = ADMIN_PAGES if is_admin else USER_PAGES
    page_key = "admin_page" if is_admin else "user_page"
    current_page = st.session_state.get(page_key)
    if current_page not in pages:
        st.session_state[page_key] = pages[0]

    selected_page = str(st.session_state[page_key])
    st.sidebar.markdown('<div class="ml-sidebar-nav-label">Навигация</div>', unsafe_allow_html=True)
    for page in pages:
        button_type = "primary" if page == selected_page else "secondary"
        if st.sidebar.button(
            page,
            key=f"{page_key}_{page}",
            type=button_type,
            width="stretch",
        ):
            st.session_state[page_key] = page
            st.rerun()

    email = str(user.get("email") or "")
    st.sidebar.markdown(
        f'<div class="ml-sidebar-footer"><div>Email</div><strong>{escape(email)}</strong></div>',
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Выйти", width="stretch"):
        for key in (
            "access_token",
            "login_error",
            "prediction_submission_result",
            "prediction_history_detail",
            "selected_prediction_model_id",
        ):
            st.session_state.pop(key, None)
        st.rerun()

    return str(selected_page)


def _render_promo_redeem(token: str) -> None:
    success_message = st.session_state.pop("promo_redeem_success", "")
    if success_message:
        st.success(success_message)

    with st.form("promo-redeem-form"):
        code = st.text_input("Промокод")
        submitted = st.form_submit_button("Активировать", type="primary")

    if not submitted:
        return

    normalized_code = code.strip()
    if not normalized_code:
        st.warning("Введите промокод.")
        return

    try:
        redemption = _redeem_promo_code(token, normalized_code)
    except DashboardApiError as exc:
        st.error(f"Промокод не активирован: {_friendly_api_error(exc)}")
        return

    credits = redemption.get("credits_granted")
    st.session_state["promo_redeem_success"] = f"Промокод активирован. Начислено: {credits}."
    st.rerun()


def _render_balance_top_up(token: str) -> None:
    success_message = st.session_state.pop("balance_top_up_success", "")
    if success_message:
        st.success(success_message)

    with st.form("balance-top-up-form"):
        credits_value = int(
            st.number_input(
                "Сколько кредитов пополнить",
                min_value=1,
                value=10,
                step=1,
            ),
        )
        st.caption("Курс обмена: 5 $ = 1 кредит")
        submitted = st.form_submit_button("Пополнить через mock-платеж", type="primary")

    if not submitted:
        return

    credits = _positive_int(credits_value)
    if credits is None:
        st.warning("Введите положительное количество кредитов.")
        return

    try:
        payment = _create_payment(token, _build_payment_payload(credits))
        payment_id = _positive_int(payment.get("id"))
        if payment_id is None:
            raise DashboardApiError("Платеж создан без корректного ID")
        confirmed = _confirm_payment(token, payment_id)
    except DashboardApiError as exc:
        st.error(f"Баланс не пополнен: {_friendly_api_error(exc)}")
        return

    credited = confirmed.get("credits_purchased", credits)
    st.session_state["balance_top_up_success"] = f"Баланс пополнен на {credited} кредитов."
    st.rerun()


def _render_user_operation_history(transactions: list[dict[str, Any]]) -> None:
    rows = _format_user_operation_rows(transactions)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("Пока нет операций по балансу.")


def _render_prediction_result(token: str) -> None:
    result = st.session_state.get("prediction_submission_result")
    if not isinstance(result, dict):
        return

    prediction_id = _positive_int(result.get("id"))
    status = str(result.get("status") or "")
    status_label = _prediction_status_label(status)

    _render_prediction_stage(status)
    if status == "succeeded":
        st.success(f"Prediction #{prediction_id} готов.")
        st.json(result.get("result_payload") or {})
    elif status == "failed":
        st.error(f"Prediction #{prediction_id}: ошибка.")
        error_message = result.get("error_message")
        if error_message:
            st.write(str(error_message))
    else:
        st.info(f"Prediction #{prediction_id}: {status_label}.")

    if prediction_id is not None and status in PENDING_PREDICTION_STATUSES:
        if st.button("Обновить результат", width="stretch"):
            try:
                st.session_state["prediction_submission_result"] = _get_prediction(
                    token,
                    prediction_id,
                )
            except DashboardApiError as exc:
                st.error(f"Не удалось обновить prediction: {_friendly_api_error(exc)}")
            else:
                st.rerun()


def _model_select_options(models: list[dict[str, Any]]) -> dict[str, int]:
    options: dict[str, int] = {}
    for model in models:
        model_id = _positive_int(model.get("id"))
        if model_id is not None:
            options[f"{model.get('name')} | ID {model_id}"] = model_id
    return options


def _render_prediction_panel(
    token: str,
    models: list[dict[str, Any]],
) -> None:
    success_message = st.session_state.pop("model_prediction_success", "")
    if success_message:
        st.success(success_message)

    with st.container(border=True):
        st.subheader("Сделать prediction")

        available_model_options = _model_select_options(models)
        if not available_model_options:
            st.info("Сначала загрузите модель на странице `Мои модели`.")
            return

        preselected_model_id = _positive_int(st.session_state.get("selected_prediction_model_id"))
        option_items = list(available_model_options.items())
        selected_index = 0
        if preselected_model_id is not None:
            for index, (_, model_id) in enumerate(option_items):
                if model_id == preselected_model_id:
                    selected_index = index
                    break

        selected_model_label = st.selectbox(
            "Модель",
            options=[label for label, _ in option_items],
            index=selected_index,
        )
        selected_model_id = available_model_options[selected_model_label]
        st.caption(f"Стоимость операции: {PREDICTION_PRICE_CREDITS} кредит.")
        data_source = st.radio(
            "Данные для prediction",
            options=["Загрузить CSV", "Ввести вручную"],
            horizontal=True,
        )

        with st.form("prediction-run-form"):
            uploaded_prediction_csv = None
            prediction_csv_has_header = False
            raw_rows = ""

            if data_source == "Загрузить CSV":
                uploaded_prediction_csv = st.file_uploader(
                    "CSV файл с данными",
                    type=["csv"],
                    key="prediction-csv-upload",
                )
                prediction_csv_has_header = st.checkbox("В первой строке есть заголовки")
            else:
                raw_rows = st.text_area(
                    "Строки данных",
                    height=120,
                    placeholder="5.1, 3.5, 1.4, 0.2\n6.2, 3.4, 5.4, 2.3",
                )

            submitted = st.form_submit_button("Запустить prediction", type="primary")

    if submitted:
        try:
            if data_source == "Загрузить CSV":
                if uploaded_prediction_csv is None:
                    st.warning("Загрузите CSV файл с данными.")
                    return
                payload = _build_prediction_payload_from_rows(
                    selected_model_id,
                    _parse_prediction_csv(
                        uploaded_prediction_csv.getvalue(),
                        has_header=prediction_csv_has_header,
                    ),
                )
            else:
                payload = _build_prediction_payload(selected_model_id, raw_rows)

            created = _create_prediction(token, payload)
            prediction_id = _positive_int(created.get("id"))
            if prediction_id is None:
                raise DashboardApiError("Prediction создан без корректного ID")

            st.session_state["prediction_submission_result"] = _wait_for_prediction_result(
                token,
                prediction_id,
            )
            st.session_state["model_prediction_success"] = "Prediction отправлен в обработку."
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
        except DashboardApiError as exc:
            st.error(f"Prediction не запущен: {_friendly_api_error(exc)}")

    _render_prediction_result(token)


def _render_model_upload_tab(token: str, models: list[dict[str, Any]]) -> None:
    success_message = st.session_state.pop("model_upload_success", "")
    if success_message:
        st.success(success_message)

    with st.container(border=True):
        st.subheader("Загрузить новую модель")
        with st.form("model-upload-form"):
            model_name = st.text_input("Название модели")
            model_description = st.text_area("Описание модели", height=80)
            uploaded_model = st.file_uploader(
                "Файл модели",
                type=["joblib", "pkl", "pickle"],
                key="model-upload-file",
            )
            submitted = st.form_submit_button("Загрузить модель", type="primary")

    if submitted:
        if uploaded_model is None:
            st.warning("Выберите файл модели.")
            return
        if not model_name.strip():
            st.warning("Введите название модели.")
            return

        try:
            uploaded = _upload_model(
                token,
                name=model_name,
                description=model_description,
                filename=uploaded_model.name,
                content=uploaded_model.getvalue(),
                content_type=_mime_type_for_upload(uploaded_model.name, uploaded_model.type),
            )
        except DashboardApiError as exc:
            st.error(f"Модель не загружена: {_friendly_api_error(exc)}")
            return

        st.session_state["model_upload_success"] = f"Модель {uploaded.get('name')} загружена."
        st.rerun()

    _render_user_models_table(models)


def _render_user_models_table(models: list[dict[str, Any]]) -> None:
    if not models:
        st.info("Пока нет загруженных моделей.")
        return

    st.subheader("Список моделей")
    columns = st.columns([0.8, 2.2, 1.4, 1.2, 1.4, 1.3, 1.1])
    for column, header in zip(
        columns,
        ["ID", "Название", "Дата загрузки", "Статус", "Фреймворк", "Prediction", "Удаление"],
        strict=True,
    ):
        column.caption(header)

    for model in models:
        model_id = _positive_int(model.get("id"))
        columns = st.columns([0.8, 2.2, 1.4, 1.2, 1.4, 1.3, 1.1])
        columns[0].write(model_id or "-")
        columns[1].write(str(model.get("name") or "-"))
        columns[2].write(_format_api_datetime(model.get("created_at")))
        columns[3].markdown(_status_badge_html(model.get("status")), unsafe_allow_html=True)
        columns[4].write(str(model.get("framework") or "-"))
        if columns[5].button(
            "Использовать",
            key=f"use-model-{model_id}",
            disabled=model_id is None,
            width="stretch",
        ):
            _navigate_user("Предсказания", selected_model_id=model_id)
        columns[6].button(
            "Удалить",
            key=f"delete-model-{model_id}",
            disabled=True,
            help="Удаление модели пока не поддержано backend API.",
            width="stretch",
        )


def _render_user_overview(token: str, data: dict[str, Any]) -> None:
    _render_page_title(
        "Обзор",
        "Главная точка входа: баланс, модели, последние predictions и быстрый запуск.",
    )
    metrics = build_dashboard_metrics(
        balance=data["balance"],
        predictions=data["predictions"],
        transactions=data["transactions"],
        payments=data["payments"],
        models=data["models"],
        redemptions=data["redemptions"],
    )

    balance_column, predictions_column, models_column = st.columns(3)
    with balance_column:
        _render_metric_card("Баланс", f"{metrics['credits_available']} кредитов")
        if st.button("Пополнить баланс", key="overview-top-up", type="primary", width="stretch"):
            _navigate_user("Баланс")
    with predictions_column:
        _render_metric_card(
            "Предсказания",
            metrics["predictions_total"],
            f"Успешных: {metrics['predictions_succeeded']}",
        )
    with models_column:
        _render_metric_card(
            "Модели",
            _active_models_total(data["models"]),
            f"Всего загружено: {metrics['models_total']}",
        )

    st.divider()
    action_column, note_column = st.columns([1, 2])
    with action_column:
        if st.button(
            "Новое предсказание",
            key="overview-new-prediction",
            type="primary",
            width="stretch",
        ):
            _navigate_user("Предсказания")
    with note_column:
        st.markdown(
            '<span class="ml-note">Prediction будет создан асинхронно. '
            "После запуска статус можно обновлять на странице предсказаний.</span>",
            unsafe_allow_html=True,
        )

    st.subheader("Последние предсказания")
    _render_prediction_table(
        data["predictions"],
        models=data["models"],
        token=token,
        limit=5,
        show_actions=False,
    )


def _render_user_predictions_page(token: str, data: dict[str, Any]) -> None:
    _render_page_title(
        "Предсказания",
        "Создайте async prediction, отследите статус и откройте историю результатов.",
    )
    _render_prediction_panel(token, data["models"])
    st.divider()
    st.subheader("История предсказаний")
    filter_label = st.radio(
        "Статус",
        options=["Все", "Успешные", "В обработке", "Ошибки"],
        horizontal=True,
        key="prediction-status-filter",
    )
    filtered_predictions = _filter_predictions_by_status(data["predictions"], filter_label)
    _render_prediction_table(
        filtered_predictions,
        models=data["models"],
        token=token,
        show_actions=True,
    )
    _render_prediction_history_detail(token)


def _render_user_models_page(token: str, data: dict[str, Any]) -> None:
    _render_page_title(
        "Мои модели",
        "Загрузка trusted Scikit-learn моделей и работа только со своими артефактами.",
    )
    _render_model_upload_tab(token, data["models"])


def _render_payment_history(payments: list[dict[str, Any]]) -> None:
    if not payments:
        st.info("Пока нет платежей.")
        return

    rows = [
        {
            "ID": payment.get("id"),
            "Дата": _format_api_datetime(payment.get("created_at")),
            "Сумма": _format_amount_cents(payment.get("amount_cents"), payment.get("currency")),
            "Кредиты": payment.get("credits_purchased"),
            "Статус": _payment_status_label(payment.get("status")),
        }
        for payment in payments
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_promo_history(redemptions: list[dict[str, Any]]) -> None:
    if not redemptions:
        st.info("Промокоды ещё не активировались.")
        return

    rows = [
        {
            "Дата": _format_api_datetime(redemption.get("created_at")),
            "Код": redemption.get("code"),
            "Начислено": redemption.get("credits_granted"),
            "Баланс после": redemption.get("balance_after_credits"),
        }
        for redemption in redemptions
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_user_balance_page(token: str, data: dict[str, Any]) -> None:
    _render_page_title(
        "Баланс",
        "Кредиты, пополнение, промокоды и полный журнал операций.",
    )
    balance = data["balance"]
    _render_metric_card("Текущий баланс", f"{_as_int(balance.get('credits_available'))} кредитов")

    top_up_column, promo_column = st.columns(2)
    with top_up_column:
        with st.container(border=True):
            st.subheader("Пополнить баланс")
            _render_balance_top_up(token)
    with promo_column:
        with st.container(border=True):
            st.subheader("Промокод")
            _render_promo_redeem(token)

    st.subheader("История операций")
    _render_user_operation_history(data["transactions"])

    payments_tab, promo_tab = st.tabs(["Платежи", "Активации промокодов"])
    with payments_tab:
        _render_payment_history(data["payments"])
    with promo_tab:
        _render_promo_history(data["redemptions"])


def _render_user_cabinet(token: str, user: dict[str, Any]) -> None:
    selected_page = _render_authenticated_sidebar(user)
    try:
        data = _load_dashboard_data(token, user)
    except DashboardApiError:
        st.error("Не удалось загрузить данные. Проверьте, что API доступен.")
        return

    if selected_page == "Обзор":
        _render_user_overview(token, data)
    elif selected_page == "Предсказания":
        _render_user_predictions_page(token, data)
    elif selected_page == "Мои модели":
        _render_user_models_page(token, data)
    elif selected_page == "Баланс":
        _render_user_balance_page(token, data)


def _user_option_labels(users: list[dict[str, Any]]) -> dict[str, int]:
    options: dict[str, int] = {}
    for user in users:
        user_id = _positive_int(user.get("id"))
        if user_id is not None:
            options[f"{user.get('email')} | ID {user_id}"] = user_id
    return options


def _admin_period_match(value: Any, period_label: str) -> bool:
    if period_label == "Все":
        return True

    parsed = _parse_api_datetime(value)
    if parsed is None:
        return False

    days_by_period = {
        "День": 1,
        "Неделя": 7,
        "Месяц": 30,
    }
    return parsed >= datetime.now(UTC) - timedelta(days=days_by_period.get(period_label, 30))


def _build_prediction_activity_chart_rows(activity: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for point in activity:
        total = _as_int(point.get("predictions_total"))
        if total <= 0:
            continue

        succeeded = _as_int(point.get("predictions_succeeded"))
        failed = _as_int(point.get("predictions_failed"))
        other = max(total - succeeded - failed, 0)
        date_label = str(point.get("date") or "-")
        label_y = total + max(total * 0.08, 0.6)

        for order, status_label, count in (
            (1, "Удача", succeeded),
            (2, "Неудача", failed),
            (3, "В обработке", other),
        ):
            if count <= 0:
                continue
            rows.append(
                {
                    "Kind": "segment",
                    "Дата": date_label,
                    "Статус": status_label,
                    "Количество": count,
                    "Порядок": order,
                    "Метка": f"{status_label}: {count}",
                    "Всего": total,
                    "LabelY": label_y,
                    "TotalLabel": "",
                },
            )

        rows.append(
            {
                "Kind": "total",
                "Дата": str(point.get("date") or "-"),
                "Статус": "Всего",
                "Количество": total,
                "Порядок": 0,
                "Метка": "",
                "Всего": total,
                "LabelY": label_y,
                "TotalLabel": str(total),
            },
        )

    return rows


def _activity_ratio(value: int, total: int) -> tuple[str, str]:
    if total <= 0:
        return "0%", "0%"

    ratio = min(max((value / total) * 100, 0), 100)
    label = f"{ratio:.1f}%".replace(".0%", "%")
    return f"{ratio:.2f}%", label


def _activity_summary_html(
    *,
    total: int,
    succeeded: int,
    failed: int,
    other: int,
) -> str:
    items = [
        ("Успешные", succeeded, "ml-activity-success"),
        ("Ошибки", failed, "ml-activity-failed"),
        ("В обработке / прочее", other, "ml-activity-other"),
    ]
    rows = []
    for label, value, class_name in items:
        width, percent_label = _activity_ratio(value, total)
        rows.append(
            (
                '<div class="ml-activity-row">'
                '<div class="ml-activity-row-head">'
                f"<span>{escape(label)}</span>"
                f"<strong>{value} · {percent_label}</strong>"
                "</div>"
                '<div class="ml-activity-track">'
                f'<div class="ml-activity-fill {class_name}" style="width: {width};"></div>'
                "</div>"
                "</div>"
            ),
        )

    return (
        '<div class="ml-activity-summary">'
        '<div class="ml-activity-title">Статусы за период</div>'
        f'<div class="ml-activity-subtitle">Всего: {total} prediction-запросов</div>'
        f"{''.join(rows)}"
        "</div>"
    )


def _render_prediction_activity_chart(activity: list[dict[str, Any]]) -> None:
    chart_rows = _build_prediction_activity_chart_rows(activity)
    if not chart_rows:
        st.info("За выбранный период нет prediction-активности.")
        return

    st.vega_lite_chart(
        chart_rows,
        {
            "height": 280,
            "layer": [
                {
                    "transform": [{"filter": "datum.Kind == 'segment'"}],
                    "mark": {"type": "bar", "cornerRadiusEnd": 3},
                    "encoding": {
                        "x": {
                            "field": "Дата",
                            "type": "ordinal",
                            "title": None,
                            "axis": {"labelAngle": 0, "labelPadding": 8},
                        },
                        "y": {
                            "field": "Количество",
                            "type": "quantitative",
                            "title": "Prediction-запросы",
                            "stack": "zero",
                            "axis": {"tickMinStep": 1, "gridColor": "rgba(248, 250, 252, 0.16)"},
                        },
                        "color": {
                            "field": "Статус",
                            "type": "nominal",
                            "title": "Статус",
                            "scale": {
                                "domain": ["Удача", "Неудача", "В обработке"],
                                "range": ["#22c55e", "#ef4444", "#f59e0b"],
                            },
                        },
                        "order": {"field": "Порядок", "type": "quantitative"},
                        "tooltip": [
                            {"field": "Дата", "type": "ordinal"},
                            {"field": "Статус", "type": "nominal"},
                            {"field": "Количество", "type": "quantitative"},
                            {"field": "Всего", "type": "quantitative"},
                        ],
                    },
                },
                {
                    "transform": [{"filter": "datum.Kind == 'segment'"}],
                    "mark": {
                        "type": "text",
                        "baseline": "middle",
                        "color": "#ffffff",
                        "fontSize": 11,
                        "fontWeight": 800,
                    },
                    "encoding": {
                        "x": {"field": "Дата", "type": "ordinal"},
                        "y": {
                            "field": "Количество",
                            "type": "quantitative",
                            "stack": "center",
                        },
                        "detail": {"field": "Статус"},
                        "text": {"field": "Метка"},
                    },
                },
                {
                    "transform": [{"filter": "datum.Kind == 'total'"}],
                    "mark": {
                        "type": "text",
                        "align": "center",
                        "baseline": "bottom",
                        "color": "#f8fafc",
                        "fontSize": 12,
                        "fontWeight": 850,
                    },
                    "encoding": {
                        "x": {"field": "Дата", "type": "ordinal"},
                        "y": {
                            "field": "LabelY",
                            "type": "quantitative",
                            "axis": {"gridColor": "rgba(248, 250, 252, 0.16)"},
                        },
                        "text": {"field": "TotalLabel"},
                    },
                },
            ],
            "background": "#0f172a",
            "config": {
                "background": "#0f172a",
                "axis": {
                    "labelColor": "#f8fafc",
                    "titleColor": "#f8fafc",
                    "domainColor": "rgba(248, 250, 252, 0.32)",
                    "tickColor": "rgba(248, 250, 252, 0.32)",
                },
                "legend": {
                    "labelColor": "#f8fafc",
                    "titleColor": "#f8fafc",
                    "orient": "top",
                },
                "view": {"stroke": "transparent"},
            },
        },
        width="stretch",
    )


def _render_admin_overview(token: str) -> None:
    _render_page_title(
        "Обзор",
        "Состояние платформы: пользователи, predictions, кредиты и последняя активность.",
        kicker="ADMIN Panel",
    )
    try:
        summary = _load_admin_summary(token)
        events = _load_admin_events(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить админские метрики: {_friendly_api_error(exc)}")
        return

    users_column, predictions_column, credits_column = st.columns(3)
    with users_column:
        _render_metric_card(
            "Пользователи",
            summary.get("users_total", 0),
            f"Активных: {summary.get('users_active', 0)}",
        )
    with predictions_column:
        _render_metric_card(
            "Predictions",
            summary.get("predictions_total", 0),
            f"Успешных: {summary.get('predictions_succeeded', 0)} "
            f"({summary.get('prediction_success_rate', 0)}%)",
        )
    with credits_column:
        _render_metric_card(
            "Кредиты списано",
            summary.get("credits_debited", 0),
            f"Начислено: {summary.get('credits_credited', 0)}; "
            f"куплено: {summary.get('credits_purchased', 0)}",
        )

    st.subheader("Активность prediction")
    period = st.radio("Период", options=["day", "week", "month"], horizontal=True)
    try:
        activity = _load_admin_activity(token, period).get("items", [])
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить активность: {_friendly_api_error(exc)}")
        activity = []
    if activity:
        _render_prediction_activity_chart(activity)
    else:
        st.info("За выбранный период нет prediction-активности.")

    st.subheader("Последняя активность")
    if not events:
        st.info("Событий пока нет.")
        return

    rows = [
        {
            "Дата": _format_api_datetime(event.get("created_at")),
            "Событие": event.get("message"),
            "Пользователь": event.get("user_email") or "-",
            "Связанный объект": event.get("related_object") or "-",
            "Уровень": event.get("severity"),
        }
        for event in events
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_admin_users_page(token: str) -> None:
    _render_page_title(
        "Пользователи",
        "Глобальный список аккаунтов, баланс и управление active/inactive статусом.",
        kicker="ADMIN Panel",
    )
    try:
        users = _load_admin_users(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить пользователей: {_friendly_api_error(exc)}")
        return

    status_filter = st.radio(
        "Статус",
        options=["Все", "Активные", "Заблокированные"],
        horizontal=True,
    )
    if status_filter == "Активные":
        visible_users = [user for user in users if bool(user.get("is_active"))]
    elif status_filter == "Заблокированные":
        visible_users = [user for user in users if not bool(user.get("is_active"))]
    else:
        visible_users = users

    rows = [
        {
            "ID": user.get("id"),
            "Пользователь": user.get("full_name") or "-",
            "Email": user.get("email"),
            "Дата регистрации": _format_api_datetime(user.get("created_at")),
            "Баланс": user.get("credits_available"),
            "Роль": user.get("role"),
            "Статус": "Активен" if user.get("is_active") else "Заблокирован",
        }
        for user in visible_users
    ]
    st.dataframe(rows, hide_index=True, width="stretch")

    if not users:
        return

    st.subheader("Открыть пользователя")
    user_options = _user_option_labels(users)
    selected_user_label = st.selectbox("Пользователь", options=list(user_options))
    selected_user_id = user_options[selected_user_label]
    try:
        detail = _load_admin_user(token, selected_user_id)
    except DashboardApiError as exc:
        st.error(f"Не удалось открыть пользователя: {_friendly_api_error(exc)}")
        return

    detail_columns = st.columns(4)
    with detail_columns[0]:
        _render_metric_card("Модели", detail.get("models_total", 0))
    with detail_columns[1]:
        _render_metric_card("Predictions", detail.get("predictions_total", 0))
    with detail_columns[2]:
        _render_metric_card("Платежи", detail.get("payments_total", 0))
    with detail_columns[3]:
        _render_metric_card("Транзакции", detail.get("transactions_total", 0))

    desired_active_state = not bool(detail.get("is_active"))
    action_label = "Разблокировать" if desired_active_state else "Заблокировать"
    if st.button(action_label, type="primary", width="stretch"):
        try:
            _update_admin_user_status(token, selected_user_id, desired_active_state)
        except DashboardApiError as exc:
            st.error(f"Статус не изменён: {_friendly_api_error(exc)}")
        else:
            st.success("Статус пользователя обновлён.")
            st.rerun()


def _render_admin_models_page(token: str) -> None:
    _render_page_title(
        "Модели",
        "Все загруженные модели, владельцы, статусы и количество запусков.",
        kicker="ADMIN Panel",
    )
    try:
        models = _load_admin_models(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить модели: {_friendly_api_error(exc)}")
        return

    rows = [
        {
            "ID": model.get("id"),
            "Название": model.get("name"),
            "Владелец": model.get("owner_email"),
            "Дата загрузки": _format_api_datetime(model.get("created_at")),
            "Статус": _status_label(model.get("status")),
            "Запусков": model.get("runs_count"),
        }
        for model in models
    ]
    st.dataframe(rows, hide_index=True, width="stretch")

    active_models = [model for model in models if model.get("status") != "deleted"]
    if not active_models:
        return

    with st.expander("Удалить проблемную модель"):
        model_options = {
            f"{model.get('name')} | {model.get('owner_email')} | ID {model.get('id')}": _as_int(
                model.get("id"),
            )
            for model in active_models
        }
        selected_label = st.selectbox("Модель", options=list(model_options))
        confirmed = st.checkbox("Подтверждаю soft-delete модели")
        if st.button("Удалить выбранную модель", type="primary", disabled=not confirmed):
            try:
                _delete_admin_model(token, model_options[selected_label])
            except DashboardApiError as exc:
                st.error(f"Модель не удалена: {_friendly_api_error(exc)}")
            else:
                st.success("Модель помечена как удалённая.")
                st.rerun()


def _render_admin_predictions_page(token: str) -> None:
    _render_page_title(
        "Предсказания",
        "Глобальная история prediction-запросов с фильтрами для поиска проблем.",
        kicker="ADMIN Panel",
    )
    try:
        predictions = _load_admin_predictions(token)
        users = _load_admin_users(token)
        models = _load_admin_models(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить predictions: {_friendly_api_error(exc)}")
        return

    user_options = {"Все": None} | _user_option_labels(users)
    model_options = {"Все": None} | {
        f"{model.get('name')} | ID {model.get('id')}": _as_int(model.get("id")) for model in models
    }
    filter_columns = st.columns(4)
    selected_user = filter_columns[0].selectbox("Пользователь", options=list(user_options))
    selected_model = filter_columns[1].selectbox("Модель", options=list(model_options))
    selected_status = filter_columns[2].selectbox(
        "Статус",
        options=["Все", "queued", "running", "succeeded", "failed"],
    )
    selected_period = filter_columns[3].selectbox(
        "Период",
        options=["Все", "День", "Неделя", "Месяц"],
    )

    visible_predictions = [
        prediction
        for prediction in predictions
        if (
            user_options[selected_user] is None
            or prediction.get("user_id") == user_options[selected_user]
        )
        and (
            model_options[selected_model] is None
            or prediction.get("model_id") == model_options[selected_model]
        )
        and (selected_status == "Все" or prediction.get("status") == selected_status)
        and _admin_period_match(prediction.get("created_at"), selected_period)
    ]
    rows = [
        {
            "ID": prediction.get("id"),
            "Пользователь": prediction.get("user_email"),
            "Модель": prediction.get("model_name"),
            "Дата": _format_api_datetime(prediction.get("created_at")),
            "Статус": _status_label(prediction.get("status")),
            "Кредиты": prediction.get("cost_credits"),
        }
        for prediction in visible_predictions
    ]
    st.dataframe(rows, hide_index=True, width="stretch")

    if not visible_predictions:
        return

    prediction_options = {
        f"Prediction #{prediction.get('id')} | {prediction.get('status')}": prediction
        for prediction in visible_predictions
    }
    selected_label = st.selectbox("Просмотр результата", options=list(prediction_options))
    selected_prediction = prediction_options[selected_label]
    if selected_prediction.get("result_payload"):
        st.json(selected_prediction.get("result_payload"))
    elif selected_prediction.get("error_message"):
        st.error(str(selected_prediction.get("error_message")))
    else:
        st.info("Результат ещё не готов.")


def _render_admin_payments_page(token: str) -> None:
    _render_page_title(
        "Платежи",
        "История mock-пополнений: сумма, кредиты, дата и статус.",
        kicker="ADMIN Panel",
    )
    try:
        payments = _load_admin_payments(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить платежи: {_friendly_api_error(exc)}")
        return

    status_filter = st.radio(
        "Статус",
        options=["Все", "succeeded", "pending", "failed"],
        horizontal=True,
    )
    visible_payments = [
        payment
        for payment in payments
        if status_filter == "Все" or payment.get("status") == status_filter
    ]
    rows = [
        {
            "ID платежа": payment.get("id"),
            "Пользователь": payment.get("user_email"),
            "Сумма": _format_amount_cents(payment.get("amount_cents"), payment.get("currency")),
            "Кредиты": payment.get("credits_purchased"),
            "Дата": _format_api_datetime(payment.get("created_at")),
            "Статус": _payment_status_label(payment.get("status")),
        }
        for payment in visible_payments
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_admin_transactions_page(token: str) -> None:
    _render_page_title(
        "Транзакции",
        "Отдельный журнал credit ledger: платежи, промокоды, списания и корректировки.",
        kicker="ADMIN Panel",
    )
    try:
        users = _load_admin_users(token)
        transactions = _load_admin_transactions(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить транзакции: {_friendly_api_error(exc)}")
        return

    with st.expander("Ручная корректировка баланса"):
        user_options = _user_option_labels(users)
        if not user_options:
            st.info("Нет пользователей для корректировки.")
        else:
            with st.form("admin-adjustment-form"):
                selected_user_label = st.selectbox("Пользователь", options=list(user_options))
                direction = st.radio("Направление", options=["credit", "debit"], horizontal=True)
                amount = int(st.number_input("Кредиты", min_value=1, value=10, step=1))
                description = st.text_input("Причина", value="Admin adjustment")
                submitted = st.form_submit_button("Создать корректировку", type="primary")

            if submitted:
                payload = {
                    "user_id": user_options[selected_user_label],
                    "direction": direction,
                    "amount_credits": amount,
                    "description": description,
                    "idempotency_key": f"dashboard-adjustment:{uuid4().hex}",
                }
                try:
                    _create_billing_adjustment(token, payload)
                except DashboardApiError as exc:
                    st.error(f"Корректировка не создана: {_friendly_api_error(exc)}")
                else:
                    st.success("Корректировка создана.")
                    st.rerun()

    type_filter = st.selectbox(
        "Тип операции",
        options=["Все", "payment_credit", "prediction_debit", "promo_credit", "adjustment"],
    )
    visible_transactions = [
        transaction
        for transaction in transactions
        if type_filter == "Все" or transaction.get("transaction_type") == type_filter
    ]
    rows = [
        {
            "Пользователь": transaction.get("user_email"),
            "Тип операции": TRANSACTION_TYPE_LABELS.get(
                str(transaction.get("transaction_type") or ""),
                transaction.get("transaction_type"),
            ),
            "Изменение": _format_credit_delta(transaction),
            "Дата": _format_api_datetime(transaction.get("created_at")),
            "Причина": transaction.get("description") or "-",
        }
        for transaction in visible_transactions
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_admin_promo_page(token: str) -> None:
    _render_page_title(
        "Промокоды",
        "Fixed-credit промокоды: создание, список и деактивация.",
        kicker="ADMIN Panel",
    )
    try:
        promo_codes = _list_items("/promo-codes", token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить промокоды: {_friendly_api_error(exc)}")
        return

    _render_admin_promo_list(promo_codes)
    _render_admin_promo_tools(token, promo_codes)


def _render_admin_settings_page(token: str) -> None:
    _render_page_title(
        "Настройки системы",
        "Безопасный read-only обзор runtime-настроек без секретов.",
        kicker="ADMIN Panel",
    )
    try:
        settings = _load_admin_settings(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить настройки: {_friendly_api_error(exc)}")
        return

    rows = [{"Параметр": key, "Значение": str(value)} for key, value in settings.items()]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.info("Редактирование настроек не включено: текущая конфигурация хранится в environment.")


def _render_admin_monitoring_page(token: str) -> None:
    _render_page_title(
        "Мониторинг",
        "Краткий summary и ссылки на существующий Prometheus/Grafana stack.",
        kicker="ADMIN Panel",
    )
    try:
        monitoring = _load_admin_monitoring(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить мониторинг: {_friendly_api_error(exc)}")
        return

    usage = monitoring.get("system_usage") or {}
    usage_columns = st.columns(3)
    with usage_columns[0]:
        _render_metric_card("CPU", usage.get("cpu_percent") or "N/A")
    with usage_columns[1]:
        _render_metric_card("RAM", usage.get("ram_percent") or "N/A")
    with usage_columns[2]:
        _render_metric_card("Disk", f"{usage.get('disk_percent', 'N/A')}%")

    services = monitoring.get("services") or []
    service_rows = [
        {
            "Сервис": service.get("name"),
            "Статус": service.get("status"),
            "Детали": service.get("details") or "-",
        }
        for service in services
    ]
    st.subheader("Services")
    st.dataframe(service_rows, hide_index=True, width="stretch")

    st.link_button("Открыть Prometheus", monitoring.get("prometheus_url"), width="stretch")
    st.link_button("Открыть Grafana", monitoring.get("grafana_url"), width="stretch")


def _render_admin_logs_page(token: str) -> None:
    _render_page_title(
        "Логи и ошибки",
        "Ошибки prediction, доступные в текущей модели данных.",
        kicker="ADMIN Panel",
    )
    try:
        logs = _load_admin_logs(token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить логи: {_friendly_api_error(exc)}")
        return

    if not logs:
        st.info("Ошибок prediction пока нет.")
        return

    rows = [
        {
            "Дата": _format_api_datetime(log.get("created_at")),
            "Уровень": log.get("level"),
            "Источник": log.get("source"),
            "Сообщение": log.get("message"),
            "Пользователь": log.get("user_email") or "-",
            "Связанный объект": log.get("related_object") or "-",
        }
        for log in logs
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_prediction_history(predictions: list[dict[str, Any]]) -> None:
    rows = _format_prediction_rows(predictions)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("Пока нет prediction-задач.")


def _render_admin_promo_list(promo_codes: list[dict[str, Any]]) -> None:
    st.subheader("Информация о промокодах")
    promo_rows = _format_admin_promo_rows(promo_codes)
    if promo_rows:
        st.dataframe(promo_rows, hide_index=True, width="stretch")
    else:
        st.info("Пока нет созданных промокодов.")


def _render_admin_promo_tools(token: str, promo_codes: list[dict[str, Any]]) -> None:
    success_message = st.session_state.pop("promo_admin_success", "")
    if success_message:
        st.success(success_message)

    st.subheader("Создать промокод")
    with st.form("promo-create-form"):
        code = st.text_input("Код")

        first_row = st.columns(2)
        credit_amount = int(
            first_row[0].number_input("Кредиты", min_value=1, value=10, step=1),
        )
        max_redemptions = int(
            first_row[1].number_input(
                "Всего активаций",
                min_value=1,
                value=100,
                step=1,
            ),
        )

        today = date.today()
        date_row = st.columns(4)
        starts_date = date_row[0].date_input("Дата начала", value=today)
        starts_time = date_row[1].time_input("Время начала", value=time(0, 0))
        expires_date = date_row[2].date_input(
            "Дата окончания",
            value=today + timedelta(days=30),
        )
        expires_time = date_row[3].time_input("Время окончания", value=time(23, 59))

        submitted = st.form_submit_button("Создать промокод", type="primary")

    if submitted:
        normalized_code = code.strip()
        starts_at = datetime.combine(starts_date, starts_time, tzinfo=UTC)
        expires_at = datetime.combine(expires_date, expires_time, tzinfo=UTC)
        if not normalized_code:
            st.warning("Введите код промокода.")
        elif starts_at >= expires_at:
            st.warning("Дата окончания должна быть позже даты начала.")
        else:
            payload = _build_promo_code_payload(
                code=normalized_code,
                credit_amount=credit_amount,
                max_redemptions=max_redemptions,
                starts_at=starts_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )

            try:
                created = _create_promo_code(token, payload)
            except DashboardApiError as exc:
                st.error(f"Промокод не создан: {_friendly_api_error(exc)}")
            else:
                st.session_state["promo_admin_success"] = f"Промокод {created.get('code')} создан."
                st.rerun()

    st.subheader("Деактивировать")
    active_options = {
        f"{promo_code.get('code')} | использований: {promo_code.get('redemptions_count', 0)}": (
            promo_code.get("id")
        )
        for promo_code in promo_codes
        if promo_code.get("is_active") and promo_code.get("id") is not None
    }

    if active_options:
        with st.form("promo-deactivate-form"):
            selected_label = st.selectbox("Промокод", options=list(active_options))
            deactivate_submitted = st.form_submit_button("Деактивировать")

        if deactivate_submitted:
            promo_code_id = _as_int(active_options[selected_label])
            try:
                deactivated = _deactivate_promo_code(token, promo_code_id)
            except DashboardApiError as exc:
                st.error(f"Промокод не деактивирован: {_friendly_api_error(exc)}")
            else:
                st.session_state["promo_admin_success"] = (
                    f"Промокод {deactivated.get('code')} деактивирован."
                )
                st.rerun()
    else:
        st.info("Нет включенных промокодов для деактивации.")


def _render_admin_dashboard(token: str, user: dict[str, Any]) -> None:
    selected_page = _render_authenticated_sidebar(user, is_admin=True)
    if selected_page == "Обзор":
        _render_admin_overview(token)
    elif selected_page == "Пользователи":
        _render_admin_users_page(token)
    elif selected_page == "Модели":
        _render_admin_models_page(token)
    elif selected_page == "Предсказания":
        _render_admin_predictions_page(token)
    elif selected_page == "Платежи":
        _render_admin_payments_page(token)
    elif selected_page == "Транзакции":
        _render_admin_transactions_page(token)
    elif selected_page == "Промокоды":
        _render_admin_promo_page(token)
    elif selected_page == "Настройки системы":
        _render_admin_settings_page(token)
    elif selected_page == "Мониторинг":
        _render_admin_monitoring_page(token)
    elif selected_page == "Логи и ошибки":
        _render_admin_logs_page(token)


def _render_tables(data: dict[str, Any], token: str) -> None:
    tab_names = [
        "Загрузить новую модель",
        "История предсказаний",
        "Пополнить баланс",
        "История операций",
    ]
    tabs = st.tabs(tab_names)
    model_upload_tab, predictions_tab, top_up_tab, history_tab = tabs[:4]

    with model_upload_tab:
        _render_model_upload_tab(token, data["models"])

    with predictions_tab:
        _render_prediction_history(data["predictions"])

    with top_up_tab:
        payment_block, promo_block = st.columns(2)
        with payment_block:
            st.subheader("Пополнить баланс")
            _render_balance_top_up(token)
        with promo_block:
            st.subheader("Активировать промокод")
            _render_promo_redeem(token)

    with history_tab:
        _render_user_operation_history(data["transactions"])


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} Dashboard", page_icon=None, layout="wide")

    token = st.session_state.get("access_token")
    is_authenticated = isinstance(token, str) and bool(token)
    _inject_dashboard_styles(hide_sidebar=not is_authenticated)
    if not is_authenticated:
        _render_login()
        return

    try:
        user = _load_current_user(token)
    except DashboardApiError:
        st.error("Не удалось загрузить данные. Проверьте, что API доступен.")
        return

    if _is_admin_user(user):
        _render_admin_dashboard(token, user)
        return

    _render_user_cabinet(token, user)


if __name__ == "__main__":
    main()
