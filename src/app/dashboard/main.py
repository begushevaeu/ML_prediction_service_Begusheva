"""Streamlit analytics dashboard entry point."""

from __future__ import annotations

import csv
import json
import mimetypes
import os
from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from time import monotonic, sleep
from typing import Any
from urllib import error, parse, request
from uuid import uuid4

import streamlit as st

from app import APP_NAME

DEFAULT_API_BASE_URL = "http://127.0.0.1:18000/api/v1"
MOCK_CENTS_PER_CREDIT = 50
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
PENDING_PREDICTION_STATUSES = {"queued", "running"}
PredictionCell = int | float | str
PredictionRows = list[list[PredictionCell]]


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


def _render_login() -> None:
    st.sidebar.header("Вход")
    with st.sidebar.expander("Настройки подключения"):
        st.session_state["api_base_url"] = st.text_input(
            "API адрес",
            value=_api_base_url(),
        )
    email = st.sidebar.text_input("Email или логин")
    password = st.sidebar.text_input("Пароль", type="password")

    if st.sidebar.button("Войти", type="primary", width="stretch"):
        try:
            st.session_state["access_token"] = _login(email, password)
            st.session_state["login_error"] = ""
        except DashboardApiError as exc:
            st.session_state["login_error"] = str(exc)

    if st.session_state.get("login_error"):
        st.sidebar.error("Не удалось войти. Проверьте email, пароль и API адрес.")

    if st.session_state.get("access_token"):
        if st.sidebar.button("Выйти", width="stretch"):
            st.session_state.pop("access_token", None)
            st.rerun()


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
            st.info("Сначала загрузите модель во вкладке `Загрузить новую модель`.")
            return

        selected_model_label = st.selectbox(
            "Модель",
            options=list(available_model_options),
        )
        selected_model_id = available_model_options[selected_model_label]
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

    model_rows = _format_rows(models, ["id", "name", "framework", "status", "created_at"])
    if model_rows:
        st.subheader("Мои модели")
        st.dataframe(model_rows, hide_index=True, width="stretch")
    else:
        st.info("Пока нет загруженных моделей.")


def _render_prediction_history(predictions: list[dict[str, Any]]) -> None:
    rows = _format_prediction_rows(predictions)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("Пока нет prediction-задач.")


def _render_admin_promo_list(promo_codes: list[dict[str, Any]]) -> None:
    st.subheader("Промокоды")
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

    _render_prediction_panel(token, data["models"])
    _render_tables(data, token)


if __name__ == "__main__":
    main()
