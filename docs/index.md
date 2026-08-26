# Documentation Index

This page is the public documentation entry point for ML Prediction Service.

## Start Here

| Document | Purpose |
| --- | --- |
| [Architecture](architecture.md) | System components, request flows, ownership boundaries, and deployment shape |
| [ERD](erd.md) | Database entity relationships and table ownership |
| [API Contracts](api.md) | Implemented REST endpoints, error envelope, and usage examples |
| [Infrastructure](infrastructure.md) | Docker Compose services, ports, volumes, and local commands |
| [Security](security.md) | Security guardrails, residual risks, and hardening notes |
| [Testing](testing.md) | Test strategy, coverage threshold, and current suite result |
| [Business Plan](business-plan.md) | Target audience, value proposition, monetization, and basic economics |

## Domain Guides

| Document | Domain |
| --- | --- |
| [Authentication](authentication.md) | Registration, login, JWT tokens, roles, and profile access |
| [Database Design](database.md) | Schema overview, constraints, indexes, and migrations |
| [ML Models](ml-models.md) | Trusted model upload, metadata, storage, and validation |
| [Predictions](predictions.md) | Async prediction lifecycle and worker execution |
| [Billing](billing.md) | Credit balance rules, ledger behavior, and idempotency |
| [Payments](payments.md) | Mock payment creation and confirmation |
| [Promo Codes](promo-codes.md) | Admin-created fixed-credit promo codes and redemption rules |
| [Dashboard](dashboard.md) | Streamlit user dashboard behavior |
| [Monitoring](monitoring.md) | Prometheus metrics and Grafana dashboard |

## Decision Records

| Document | Purpose |
| --- | --- |
| [Architecture Decisions](architecture-decisions.md) | Agreed implementation choices and deferred decisions |
| [Foundation](foundation.md) | Initial package boundaries and local quality pipeline |

## Local URLs

When Docker Compose is running, the main local URLs are:

| Area | URL |
| --- | --- |
| API docs | `http://127.0.0.1:18000/docs` |
| Backend health | `http://127.0.0.1:18000/api/v1/health` |
| User dashboard | `http://127.0.0.1:18501` |
| Metrics endpoint | `http://127.0.0.1:18000/metrics` |
| Prometheus | `http://127.0.0.1:19090` |
| Grafana | `http://127.0.0.1:13000` |
