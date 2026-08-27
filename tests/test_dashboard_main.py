"""Streamlit dashboard helper tests."""

import json
from datetime import UTC, date, datetime, time

import pytest

from app.dashboard.main import (
    DashboardApiError,
    _build_model_upload_fields,
    _build_payment_payload,
    _build_prediction_activity_chart_rows,
    _build_prediction_payload,
    _build_prediction_payload_from_rows,
    _build_promo_code_payload,
    _combine_datetime,
    _format_admin_promo_rows,
    _format_prediction_rows,
    _format_user_operation_rows,
    _friendly_api_error,
    _is_admin,
    _mime_type_for_upload,
    _model_select_options,
    _parse_prediction_csv,
    _parse_prediction_rows,
    _promo_code_status,
)


def test_is_admin_detects_admin_user_role() -> None:
    assert _is_admin({"user": {"role": "admin"}})
    assert not _is_admin({"user": {"role": "user"}})
    assert not _is_admin({"user": {}})


def test_combine_datetime_returns_utc_iso_value() -> None:
    assert _combine_datetime(date(2026, 8, 27), time(14, 30)) == "2026-08-27T14:30:00+00:00"


def test_build_promo_code_payload_includes_required_total_limit_and_dates() -> None:
    payload = _build_promo_code_payload(
        code=" welcome100 ",
        credit_amount=100,
        max_redemptions=10,
        starts_at="2026-08-27T00:00:00+00:00",
        expires_at="2026-09-27T00:00:00+00:00",
    )

    assert payload == {
        "code": "WELCOME100",
        "credit_amount": 100,
        "is_active": True,
        "max_redemptions": 10,
        "starts_at": "2026-08-27T00:00:00+00:00",
        "expires_at": "2026-09-27T00:00:00+00:00",
    }


def test_build_promo_code_payload_normalizes_code() -> None:
    payload = _build_promo_code_payload(
        code=" open ",
        credit_amount=5,
        max_redemptions=50,
        starts_at="2026-08-27T00:00:00+00:00",
        expires_at="2026-09-27T00:00:00+00:00",
    )

    assert payload == {
        "code": "OPEN",
        "credit_amount": 5,
        "is_active": True,
        "max_redemptions": 50,
        "starts_at": "2026-08-27T00:00:00+00:00",
        "expires_at": "2026-09-27T00:00:00+00:00",
    }


def test_build_payment_payload_uses_mock_credit_price() -> None:
    assert _build_payment_payload(12) == {
        "credits_purchased": 12,
        "amount_cents": 600,
        "currency": "USD",
    }


def test_build_prediction_activity_chart_rows_adds_segments_and_total_label() -> None:
    rows = _build_prediction_activity_chart_rows(
        [
            {
                "date": "2026-08-27",
                "predictions_total": 5,
                "predictions_succeeded": 3,
                "predictions_failed": 1,
            },
            {
                "date": "2026-08-28",
                "predictions_total": 0,
                "predictions_succeeded": 0,
                "predictions_failed": 0,
            },
        ],
    )

    assert [(row["Kind"], row["Статус"], row["Количество"]) for row in rows] == [
        ("segment", "Удача", 3),
        ("segment", "Неудача", 1),
        ("segment", "В обработке", 1),
        ("total", "Всего", 5),
    ]
    assert rows[-1]["TotalLabel"] == "5"


def test_parse_prediction_rows_accepts_friendly_csv_input() -> None:
    assert _parse_prediction_rows("1, 2.5, vip\n3;4;5") == [
        [1, 2.5, "vip"],
        [3, 4, 5],
    ]


def test_parse_prediction_rows_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="хотя бы одну строку"):
        _parse_prediction_rows(" \n ")


def test_parse_prediction_csv_accepts_header_and_semicolon_separator() -> None:
    content = b"feature_a;feature_b;segment\n1;2.5;vip\n3;4;regular\n"

    assert _parse_prediction_csv(content, has_header=True) == [
        [1, 2.5, "vip"],
        [3, 4, "regular"],
    ]


def test_parse_prediction_csv_rejects_empty_file() -> None:
    with pytest.raises(ValueError, match="CSV должен содержать"):
        _parse_prediction_csv(b"\n\n")


def test_build_prediction_payload_uses_rows_contract() -> None:
    assert _build_prediction_payload(7, "1,2\n3,4") == {
        "model_id": 7,
        "input_payload": {"rows": [[1, 2], [3, 4]]},
    }


def test_build_prediction_payload_from_rows_uses_uploaded_csv_rows() -> None:
    assert _build_prediction_payload_from_rows(7, [[1, 2], [3, 4]]) == {
        "model_id": 7,
        "input_payload": {"rows": [[1, 2], [3, 4]]},
    }


def test_build_model_upload_fields_keeps_description_as_metadata() -> None:
    fields = _build_model_upload_fields(name=" Churn ", description="Demo model")

    assert fields["name"] == "Churn"
    assert fields["framework"] == "scikit-learn"
    assert json.loads(fields["metadata_json"]) == {"description": "Demo model"}


def test_model_select_options_use_uploaded_model_names_and_ids() -> None:
    assert _model_select_options(
        [
            {"id": 7, "name": "Churn"},
            {"id": None, "name": "Broken"},
            {"id": "oops", "name": "Invalid"},
        ],
    ) == {"Churn | ID 7": 7}


def test_mime_type_for_upload_falls_back_to_binary() -> None:
    assert _mime_type_for_upload("model.joblib", "application/octet-stream") == (
        "application/octet-stream"
    )
    assert _mime_type_for_upload("model.unknown", None) == "application/octet-stream"


def test_promo_code_status_uses_dates_limits_and_active_flag() -> None:
    now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

    assert (
        _promo_code_status(
            {
                "is_active": True,
                "starts_at": "2026-08-27T00:00:00+00:00",
                "expires_at": "2026-08-28T00:00:00+00:00",
                "redemptions_count": 0,
                "max_redemptions": 1,
            },
            now=now,
        )
        == "Активен"
    )
    assert _promo_code_status({"is_active": False}, now=now) == "Отключен"
    assert (
        _promo_code_status(
            {"is_active": True, "starts_at": "2026-08-28T00:00:00+00:00"},
            now=now,
        )
        == "Запланирован"
    )
    assert (
        _promo_code_status(
            {"is_active": True, "expires_at": "2026-08-27T12:00:00+00:00"},
            now=now,
        )
        == "Истек"
    )
    assert (
        _promo_code_status(
            {"is_active": True, "redemptions_count": 2, "max_redemptions": 2},
            now=now,
        )
        == "Лимит исчерпан"
    )


def test_format_admin_promo_rows_adds_issued_credits() -> None:
    rows = _format_admin_promo_rows(
        [
            {
                "id": 7,
                "code": "WELCOME",
                "credit_amount": 25,
                "redemptions_count": 4,
                "max_redemptions": 100,
                "is_active": True,
                "starts_at": "2026-08-27T00:00:00+00:00",
                "expires_at": "2026-09-27T00:00:00+00:00",
            },
        ],
    )

    assert rows[0]["Код"] == "WELCOME"
    assert "На пользователя" not in rows[0]
    assert rows[0]["Использовано всего"] == 4
    assert rows[0]["Выдано кредитов"] == 100
    assert rows[0]["Общий лимит"] == "100"


def test_format_admin_promo_rows_marks_missing_total_limit() -> None:
    rows = _format_admin_promo_rows(
        [
            {
                "id": 8,
                "code": "LEGACY",
                "credit_amount": 15,
                "redemptions_count": 0,
                "max_redemptions": None,
                "is_active": True,
                "starts_at": "2026-08-27T00:00:00+00:00",
                "expires_at": "2026-09-27T00:00:00+00:00",
            },
        ],
    )

    assert "На пользователя" not in rows[0]
    assert rows[0]["Общий лимит"] == "Не задан"


def test_format_user_operation_rows_merges_balance_history() -> None:
    rows = _format_user_operation_rows(
        [
            {
                "transaction_type": "payment_credit",
                "direction": "credit",
                "amount_credits": 10,
                "balance_after_credits": 10,
                "status": "posted",
                "created_at": "2026-08-27T10:00:00+00:00",
            },
            {
                "transaction_type": "promo_credit",
                "direction": "credit",
                "amount_credits": 5,
                "balance_after_credits": 15,
                "status": "posted",
                "created_at": "2026-08-27T11:00:00+00:00",
            },
            {
                "transaction_type": "prediction_debit",
                "direction": "debit",
                "amount_credits": 1,
                "balance_after_credits": 14,
                "status": "posted",
                "created_at": "2026-08-27T12:00:00+00:00",
            },
        ],
    )

    assert rows == [
        {
            "Дата": "2026-08-27 10:00",
            "Операция": "Пополнение баланса",
            "Изменение": "+10",
            "Баланс после": 10,
            "Статус": "Готово",
        },
        {
            "Дата": "2026-08-27 11:00",
            "Операция": "Промокод",
            "Изменение": "+5",
            "Баланс после": 15,
            "Статус": "Готово",
        },
        {
            "Дата": "2026-08-27 12:00",
            "Операция": "Списание за prediction",
            "Изменение": "-1",
            "Баланс после": 14,
            "Статус": "Готово",
        },
    ]


def test_format_prediction_rows_uses_friendly_status_and_result() -> None:
    rows = _format_prediction_rows(
        [
            {
                "id": 3,
                "model_id": 9,
                "status": "succeeded",
                "result_payload": {"predictions": [15.0]},
                "error_message": None,
                "created_at": "2026-08-27T12:00:00+00:00",
            },
        ],
    )

    assert rows == [
        {
            "Дата": "2026-08-27 12:00",
            "ID": 3,
            "Модель": 9,
            "Статус": "Готово",
            "Результат": '{"predictions": [15.0]}',
            "Ошибка": "-",
        },
    ]


def test_friendly_api_error_prefers_error_message() -> None:
    error = DashboardApiError(
        '{"error": {"code": "promo_code_exists", "message": "Promo code already exists"}}',
    )

    assert _friendly_api_error(error) == "Promo code already exists"


def test_friendly_api_error_falls_back_to_raw_text() -> None:
    assert _friendly_api_error(DashboardApiError("connection refused")) == "connection refused"
