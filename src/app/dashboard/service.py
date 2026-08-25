"""Dashboard aggregation helpers."""

from collections import Counter
from typing import Any


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0


def summarize_predictions(predictions: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize prediction task statuses."""

    counts = Counter(str(item.get("status") or "unknown") for item in predictions)
    return {
        "total": len(predictions),
        "queued": counts["queued"],
        "running": counts["running"],
        "succeeded": counts["succeeded"],
        "failed": counts["failed"],
    }


def summarize_transactions(transactions: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize credit ledger activity."""

    credited = 0
    debited = 0
    payment_credits = 0
    promo_credits = 0
    prediction_debits = 0

    for item in transactions:
        amount = _as_int(item.get("amount_credits"))
        direction = item.get("direction")
        transaction_type = item.get("transaction_type")

        if direction == "credit":
            credited += amount
        elif direction == "debit":
            debited += amount

        if transaction_type == "payment_credit":
            payment_credits += amount
        elif transaction_type == "promo_credit":
            promo_credits += amount
        elif transaction_type == "prediction_debit":
            prediction_debits += amount

    return {
        "credited": credited,
        "debited": debited,
        "net": credited - debited,
        "payment_credits": payment_credits,
        "promo_credits": promo_credits,
        "prediction_debits": prediction_debits,
    }


def build_dashboard_metrics(
    *,
    balance: dict[str, Any],
    predictions: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    models: list[dict[str, Any]],
    redemptions: list[dict[str, Any]],
) -> dict[str, int]:
    """Build top-level metrics for the Streamlit dashboard."""

    prediction_summary = summarize_predictions(predictions)
    transaction_summary = summarize_transactions(transactions)
    succeeded_payments = [payment for payment in payments if payment.get("status") == "succeeded"]

    return {
        "credits_available": _as_int(balance.get("credits_available")),
        "models_total": len(models),
        "predictions_total": prediction_summary["total"],
        "predictions_succeeded": prediction_summary["succeeded"],
        "predictions_failed": prediction_summary["failed"],
        "credits_added": transaction_summary["credited"],
        "credits_spent": transaction_summary["debited"],
        "payment_credits": transaction_summary["payment_credits"],
        "promo_credits": transaction_summary["promo_credits"],
        "successful_payments": len(succeeded_payments),
        "promo_redemptions": len(redemptions),
    }


__all__ = [
    "build_dashboard_metrics",
    "summarize_predictions",
    "summarize_transactions",
]
