"""Streamlit analytics dashboard entry point."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, time, timedelta
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
    "credit_amount": "Кредиты",
    "max_redemptions": "Лимит",
    "redemptions_count": "Активации",
    "is_active": "Активен",
    "credits_granted": "Начислено",
    "starts_at": "Начало",
    "expires_at": "Окончание",
    "updated_at": "Обновлено",
}


class DashboardApiError(RuntimeError):
    """Raised when the dashboard API request fails."""


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
            "Общий лимит": promo_code.get("max_redemptions") or "Не задан",
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


def _render_login() -> None:
    st.sidebar.header("Вход")
    with st.sidebar.expander("Настройки подключения"):
        st.session_state["api_base_url"] = st.text_input(
            "API адрес",
            value=_api_base_url(),
        )
    email = st.sidebar.text_input("Email или логин")
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


def _render_admin_promo_list(promo_codes: list[dict[str, Any]]) -> None:
    st.subheader("Промокоды")
    promo_rows = _format_admin_promo_rows(promo_codes)
    if promo_rows:
        st.dataframe(promo_rows, hide_index=True, use_container_width=True)
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
    st.caption("Админ-режим")
    email = user.get("email")
    if email:
        st.caption(str(email))

    try:
        promo_codes = _list_items("/promo-codes", token)
    except DashboardApiError as exc:
        st.error(f"Не удалось загрузить промокоды: {_friendly_api_error(exc)}")
        return

    _render_admin_promo_list(promo_codes)
    _render_admin_promo_tools(token, promo_codes)


def _render_tables(data: dict[str, Any], token: str) -> None:
    tab_names = ["Обзор", "Предсказания", "Биллинг", "Модели", "Платежи и промо"]
    tabs = st.tabs(tab_names)
    overview_tab, predictions_tab, billing_tab, models_tab, money_tab = tabs[:5]

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
    _render_login()

    token = st.session_state.get("access_token")
    if not isinstance(token, str) or not token:
        st.info("Войдите, чтобы увидеть данные аккаунта.")
        return

    try:
        user = _load_current_user(token)
    except DashboardApiError:
        st.error("Не удалось загрузить данные. Проверьте, что API доступен.")
        return

    if _is_admin_user(user):
        _render_admin_dashboard(token, user)
        return

    st.caption("Пользовательская аналитика")
    try:
        data = _load_dashboard_data(token, user)
    except DashboardApiError:
        st.error("Не удалось загрузить данные. Проверьте, что API доступен.")
        return

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
    _render_tables(data, token)


if __name__ == "__main__":
    main()
