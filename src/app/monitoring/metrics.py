"""Prometheus-compatible metrics helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from threading import Lock

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    BillingTransaction,
    CreditBalance,
    MLModel,
    Payment,
    PredictionTask,
    PromoRedemption,
)

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
RequestKey = tuple[str, str, str]


class MetricsRegistry:
    """Small in-process metrics registry for HTTP request counters."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: Counter[RequestKey] = Counter()
        self._error_counts: Counter[RequestKey] = Counter()
        self._request_duration_sums: defaultdict[RequestKey, float] = defaultdict(float)

    def record_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        key = (method.upper(), path, str(status_code))
        with self._lock:
            self._request_counts[key] += 1
            self._request_duration_sums[key] += max(duration_seconds, 0.0)
            if status_code >= 400:
                self._error_counts[key] += 1

    def snapshot(
        self,
    ) -> tuple[
        Counter[RequestKey],
        Counter[RequestKey],
        dict[RequestKey, float],
    ]:
        with self._lock:
            return (
                self._request_counts.copy(),
                self._error_counts.copy(),
                dict(self._request_duration_sums),
            )

    def reset(self) -> None:
        with self._lock:
            self._request_counts.clear()
            self._error_counts.clear()
            self._request_duration_sums.clear()


_REGISTRY = MetricsRegistry()


def _escape_label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(labels: Mapping[str, object] | None) -> str:
    if not labels:
        return ""
    rendered = ",".join(f'{key}="{_escape_label(value)}"' for key, value in sorted(labels.items()))
    return f"{{{rendered}}}"


def _value(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _append_help(lines: list[str], name: str, help_text: str, metric_type: str) -> None:
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} {metric_type}")


def _append_metric(
    lines: list[str],
    name: str,
    value: int | float,
    labels: Mapping[str, object] | None = None,
) -> None:
    lines.append(f"{name}{_labels(labels)} {_value(value)}")


def _counts_by_column(session: Session, column: object) -> dict[str, int]:
    rows = session.execute(select(column, func.count()).group_by(column)).all()
    return {str(value): int(count) for value, count in rows}


def _append_http_metrics(lines: list[str]) -> None:
    request_counts, error_counts, request_duration_sums = _REGISTRY.snapshot()

    _append_help(lines, "ml_http_requests_total", "Total HTTP requests.", "counter")
    for (method, path, status_code), count in sorted(request_counts.items()):
        _append_metric(
            lines,
            "ml_http_requests_total",
            count,
            {"method": method, "path": path, "status_code": status_code},
        )

    _append_help(
        lines,
        "ml_http_request_errors_total",
        "Total HTTP requests with 4xx or 5xx status codes.",
        "counter",
    )
    for (method, path, status_code), count in sorted(error_counts.items()):
        _append_metric(
            lines,
            "ml_http_request_errors_total",
            count,
            {"method": method, "path": path, "status_code": status_code},
        )

    _append_help(
        lines,
        "ml_http_request_duration_seconds",
        "HTTP request duration summary.",
        "summary",
    )
    for key, count in sorted(request_counts.items()):
        method, path, status_code = key
        labels = {"method": method, "path": path, "status_code": status_code}
        _append_metric(lines, "ml_http_request_duration_seconds_count", count, labels)
        _append_metric(
            lines,
            "ml_http_request_duration_seconds_sum",
            request_duration_sums.get(key, 0.0),
            labels,
        )


def _append_prediction_metrics(lines: list[str], session: Session) -> None:
    statuses = _counts_by_column(session, PredictionTask.status)

    _append_help(lines, "ml_prediction_tasks", "Prediction tasks by status.", "gauge")
    for status in ("pending", "queued", "running", "succeeded", "failed"):
        _append_metric(
            lines,
            "ml_prediction_tasks",
            statuses.get(status, 0),
            {"status": status},
        )

    _append_help(
        lines,
        "ml_worker_prediction_tasks_completed",
        "Prediction tasks completed by the worker.",
        "gauge",
    )
    for status in ("succeeded", "failed"):
        _append_metric(
            lines,
            "ml_worker_prediction_tasks_completed",
            statuses.get(status, 0),
            {"status": status},
        )


def _append_billing_metrics(lines: list[str], session: Session) -> None:
    _append_help(lines, "ml_credit_balance_available", "Total available credits.", "gauge")
    credits_available = session.scalar(
        select(func.coalesce(func.sum(CreditBalance.credits_available), 0)),
    )
    _append_metric(lines, "ml_credit_balance_available", int(credits_available or 0))

    rows = session.execute(
        select(
            BillingTransaction.transaction_type,
            BillingTransaction.direction,
            BillingTransaction.status,
            func.count(),
            func.coalesce(func.sum(BillingTransaction.amount_credits), 0),
        ).group_by(
            BillingTransaction.transaction_type,
            BillingTransaction.direction,
            BillingTransaction.status,
        ),
    ).all()

    _append_help(lines, "ml_billing_transactions", "Billing transactions by type.", "gauge")
    _append_help(lines, "ml_billing_credit_amount", "Billing credit amount by type.", "gauge")
    for transaction_type, direction, status, count, amount in rows:
        labels = {
            "direction": direction,
            "status": status,
            "transaction_type": transaction_type,
        }
        _append_metric(lines, "ml_billing_transactions", int(count), labels)
        _append_metric(lines, "ml_billing_credit_amount", int(amount), labels)


def _append_domain_metrics(lines: list[str], session: Session) -> None:
    model_statuses = _counts_by_column(session, MLModel.status)
    payment_statuses = _counts_by_column(session, Payment.status)

    _append_help(lines, "ml_models", "Uploaded models by status.", "gauge")
    for status in ("uploaded", "failed"):
        _append_metric(lines, "ml_models", model_statuses.get(status, 0), {"status": status})

    _append_help(lines, "ml_payments", "Payments by status.", "gauge")
    for status in ("pending", "succeeded", "failed"):
        _append_metric(lines, "ml_payments", payment_statuses.get(status, 0), {"status": status})

    _append_help(lines, "ml_promo_redemptions", "Total promo code redemptions.", "gauge")
    redemptions = session.scalar(select(func.count(PromoRedemption.id)))
    _append_metric(lines, "ml_promo_redemptions", int(redemptions or 0))


def record_http_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record one completed HTTP request."""

    _REGISTRY.record_http_request(
        method=method,
        path=path,
        status_code=status_code,
        duration_seconds=duration_seconds,
    )


def render_prometheus_metrics(session: Session) -> str:
    """Render current runtime and database metrics in Prometheus text format."""

    lines: list[str] = []
    _append_http_metrics(lines)
    _append_prediction_metrics(lines, session)
    _append_billing_metrics(lines, session)
    _append_domain_metrics(lines, session)
    lines.append("")
    return "\n".join(lines)


def reset_metrics_for_tests() -> None:
    """Reset in-process metrics between tests."""

    _REGISTRY.reset()


__all__ = [
    "PROMETHEUS_CONTENT_TYPE",
    "record_http_request",
    "render_prometheus_metrics",
    "reset_metrics_for_tests",
]
