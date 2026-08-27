"""Streamlit dashboard helper tests."""

from datetime import UTC, date, datetime, time

from app.dashboard.main import (
    DashboardApiError,
    _build_promo_code_payload,
    _combine_datetime,
    _format_admin_promo_rows,
    _friendly_api_error,
    _is_admin,
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
    assert rows[0]["Общий лимит"] == 100


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


def test_friendly_api_error_prefers_error_message() -> None:
    error = DashboardApiError(
        '{"error": {"code": "promo_code_exists", "message": "Promo code already exists"}}',
    )

    assert _friendly_api_error(error) == "Promo code already exists"


def test_friendly_api_error_falls_back_to_raw_text() -> None:
    assert _friendly_api_error(DashboardApiError("connection refused")) == "connection refused"
