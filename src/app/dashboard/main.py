"""Streamlit analytics dashboard entry point."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, parse, request

import streamlit as st

from app import APP_NAME
from app.dashboard.service import (
    build_dashboard_metrics,
    summarize_predictions,
    summarize_transactions,
)

DEFAULT_API_BASE_URL = "http://127.0.0.1:18000/api/v1"
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
    "credits_granted": "Начислено",
}


class DashboardApiError(RuntimeError):
    """Raised when the dashboard API request fails."""


def _api_base_url() -> str:
    return str(
        st.session_state.get("api_base_url") or os.getenv("API_BASE_URL") or DEFAULT_API_BASE_URL,
    )


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


def _load_dashboard_data(token: str) -> dict[str, Any]:
    return {
        "user": _request_json("/users/me", token=token),
        "balance": _request_json("/billing/balance", token=token),
        "transactions": _list_items("/billing/transactions", token),
        "payments": _list_items("/payments", token),
        "predictions": _list_items("/predictions", token),
        "models": _list_items("/models", token),
        "redemptions": _list_items("/promo-codes/redemptions", token),
    }


def _format_rows(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    return [{COLUMN_LABELS.get(field, field): row.get(field) for field in fields} for row in rows]


def _render_login() -> None:
    st.sidebar.header("Вход")
    with st.sidebar.expander("Настройки подключения"):
        st.session_state["api_base_url"] = st.text_input(
            "API адрес",
            value=_api_base_url(),
        )
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Пароль", type="password")

    if st.sidebar.button("Войти", type="primary", use_container_width=True):
        try:
            st.session_state["access_token"] = _login(email, password)
            st.session_state["login_error"] = ""
        except DashboardApiError as exc:
            st.session_state["login_error"] = str(exc)

    if st.session_state.get("login_error"):
        st.sidebar.error("Не удалось войти. Проверьте email, пароль и API адрес.")

    if st.session_state.get("access_token"):
        if st.sidebar.button("Выйти", use_container_width=True):
            st.session_state.pop("access_token", None)
            st.rerun()


def _render_metric_grid(metrics: dict[str, int]) -> None:
    columns = st.columns(6)
    columns[0].metric("Баланс", metrics["credits_available"])
    columns[1].metric("Задачи", metrics["predictions_total"])
    columns[2].metric("Успешно", metrics["predictions_succeeded"])
    columns[3].metric("Ошибки", metrics["predictions_failed"])
    columns[4].metric("Потрачено", metrics["credits_spent"])
    columns[5].metric("Модели", metrics["models_total"])

    columns = st.columns(4)
    columns[0].metric("Пополнено", metrics["credits_added"])
    columns[1].metric("Платежи", metrics["successful_payments"])
    columns[2].metric("Промокоды", metrics["promo_redemptions"])
    columns[3].metric("Промо-кредиты", metrics["promo_credits"])


def _render_overview(data: dict[str, Any]) -> None:
    predictions = data["predictions"]
    transactions = data["transactions"]
    prediction_summary = summarize_predictions(predictions)
    transaction_summary = summarize_transactions(transactions)

    left, right = st.columns(2)
    with left:
        st.subheader("Статусы prediction")
        status_rows = [
            {"status": status, "count": count}
            for status, count in prediction_summary.items()
            if status != "total"
        ]
        st.dataframe(status_rows, hide_index=True, use_container_width=True)
    with right:
        st.subheader("Кредиты")
        credit_rows = [
            {"metric": "Начислено", "credits": transaction_summary["credited"]},
            {"metric": "Списано", "credits": transaction_summary["debited"]},
            {"metric": "Платежи", "credits": transaction_summary["payment_credits"]},
            {"metric": "Промокоды", "credits": transaction_summary["promo_credits"]},
        ]
        st.dataframe(credit_rows, hide_index=True, use_container_width=True)


def _render_tables(data: dict[str, Any]) -> None:
    overview_tab, predictions_tab, billing_tab, models_tab, money_tab = st.tabs(
        ["Обзор", "Предсказания", "Биллинг", "Модели", "Платежи и промо"],
    )

    with overview_tab:
        _render_overview(data)

    with predictions_tab:
        st.dataframe(
            _format_rows(
                data["predictions"],
                ["id", "model_id", "status", "result_payload", "error_message", "created_at"],
            ),
            hide_index=True,
            use_container_width=True,
        )

    with billing_tab:
        st.dataframe(
            _format_rows(
                data["transactions"],
                [
                    "id",
                    "transaction_type",
                    "direction",
                    "amount_credits",
                    "balance_after_credits",
                    "created_at",
                ],
            ),
            hide_index=True,
            use_container_width=True,
        )

    with models_tab:
        st.dataframe(
            _format_rows(data["models"], ["id", "name", "framework", "status", "created_at"]),
            hide_index=True,
            use_container_width=True,
        )

    with money_tab:
        st.subheader("Платежи")
        st.dataframe(
            _format_rows(
                data["payments"],
                ["id", "status", "credits_purchased", "amount_cents", "currency", "created_at"],
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.subheader("Промокоды")
        st.dataframe(
            _format_rows(data["redemptions"], ["id", "code", "credits_granted", "created_at"]),
            hide_index=True,
            use_container_width=True,
        )


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} Dashboard", page_icon=None, layout="wide")
    st.title(APP_NAME)
    st.caption("Пользовательская аналитика")
    _render_login()

    token = st.session_state.get("access_token")
    if not isinstance(token, str) or not token:
        st.info("Войдите, чтобы увидеть данные аккаунта.")
        return

    try:
        data = _load_dashboard_data(token)
    except DashboardApiError:
        st.error("Не удалось загрузить данные. Проверьте, что API доступен.")
        return

    user = data["user"]
    email = user.get("email") if isinstance(user, dict) else None
    if email:
        st.caption(str(email))

    metrics = build_dashboard_metrics(
        balance=data["balance"],
        predictions=data["predictions"],
        transactions=data["transactions"],
        payments=data["payments"],
        models=data["models"],
        redemptions=data["redemptions"],
    )
    _render_metric_grid(metrics)
    _render_tables(data)


if __name__ == "__main__":
    main()
