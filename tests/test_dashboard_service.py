"""Dashboard aggregation tests."""

from app.dashboard.service import (
    build_dashboard_metrics,
    summarize_predictions,
    summarize_transactions,
)


def test_summarize_predictions_counts_statuses() -> None:
    summary = summarize_predictions(
        [
            {"status": "queued"},
            {"status": "running"},
            {"status": "succeeded"},
            {"status": "succeeded"},
            {"status": "failed"},
        ],
    )

    assert summary == {
        "total": 5,
        "queued": 1,
        "running": 1,
        "succeeded": 2,
        "failed": 1,
    }


def test_summarize_transactions_calculates_credit_totals() -> None:
    summary = summarize_transactions(
        [
            {
                "transaction_type": "payment_credit",
                "direction": "credit",
                "amount_credits": 10,
            },
            {
                "transaction_type": "promo_credit",
                "direction": "credit",
                "amount_credits": "4",
            },
            {
                "transaction_type": "prediction_debit",
                "direction": "debit",
                "amount_credits": 3,
            },
        ],
    )

    assert summary == {
        "credited": 14,
        "debited": 3,
        "net": 11,
        "payment_credits": 10,
        "promo_credits": 4,
        "prediction_debits": 3,
    }


def test_build_dashboard_metrics_combines_api_payloads() -> None:
    metrics = build_dashboard_metrics(
        balance={"credits_available": "12"},
        predictions=[
            {"status": "succeeded"},
            {"status": "failed"},
            {"status": "queued"},
        ],
        transactions=[
            {
                "transaction_type": "payment_credit",
                "direction": "credit",
                "amount_credits": 10,
            },
            {
                "transaction_type": "promo_credit",
                "direction": "credit",
                "amount_credits": 5,
            },
            {
                "transaction_type": "prediction_debit",
                "direction": "debit",
                "amount_credits": 3,
            },
        ],
        payments=[
            {"status": "succeeded"},
            {"status": "pending"},
        ],
        models=[
            {"id": 1},
            {"id": 2},
        ],
        redemptions=[
            {"id": 1},
        ],
    )

    assert metrics == {
        "credits_available": 12,
        "models_total": 2,
        "predictions_total": 3,
        "predictions_succeeded": 1,
        "predictions_failed": 1,
        "credits_added": 15,
        "credits_spent": 3,
        "payment_credits": 10,
        "promo_credits": 5,
        "successful_payments": 1,
        "promo_redemptions": 1,
    }
