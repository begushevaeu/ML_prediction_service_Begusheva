# Business Plan

This short business plan summarizes the product, market, monetization model, and
basic economics for ML Prediction Service. It is aligned with the implemented
MVP rather than an imagined production system.

## Executive Summary

ML Prediction Service is a self-service platform where users upload trusted
Scikit-learn models, run asynchronous predictions through an API, and pay for
successful predictions with prepaid credits.

The MVP proves the core commercial loop:

1. User registers and logs in.
2. User uploads a trusted ML model.
3. User tops up credits through a mock payment flow.
4. User runs predictions asynchronously.
5. Successful predictions debit credits.
6. User monitors usage, balance, and spending in a dashboard.
7. Promo codes can grant bonus credits for acquisition or retention campaigns.

## Problem

Small teams, students, analysts, and internal business units often have trained
ML models but lack a simple service layer for:

- authenticated API access;
- asynchronous prediction execution;
- per-request billing;
- usage analytics;
- monitoring and operational visibility.

Without this layer, each team repeats the same infrastructure work before a
model can become a usable product.

## Target Audience

| Segment | Need |
| --- | --- |
| Student and educational ML teams | Demonstrate production-like ML delivery without enterprise infrastructure |
| Small data teams | Expose internal models through a controlled API |
| Consultants and prototype builders | Package client-specific models behind a reusable service shell |
| Internal business units | Track model usage and credit-like cost allocation between teams |

The first realistic market for this MVP is educational and prototype use. A
production version would need stronger payment, upload isolation, and deployment
controls before serving untrusted external customers.

## Value Proposition

The service turns a trained Scikit-learn model into an authenticated,
observable, credit-billed prediction API.

Core benefits:

- faster path from model artifact to usable API;
- built-in JWT authentication and ownership boundaries;
- asynchronous execution so the API is not blocked by model runtime;
- credit ledger that records each balance change;
- user dashboard for prediction statistics and credit spending;
- Prometheus/Grafana monitoring for technical operations;
- promo code mechanic for simple growth campaigns.

## Product Scope

Implemented MVP capabilities:

- user registration and JWT login;
- `user` and `admin` roles;
- trusted Scikit-learn/joblib/pickle model upload;
- asynchronous prediction lifecycle through Celery and Redis;
- PostgreSQL-backed credit balance and immutable transaction ledger;
- successful-prediction billing;
- failed predictions are not charged;
- mock payments for balance top-up;
- fixed-credit promo codes with activation limits;
- Streamlit user analytics dashboard;
- Prometheus metrics and Grafana dashboard;
- automated tests with coverage above 70%.

Explicit MVP limitations:

- payments are mock/sandbox only;
- credit package catalog is deferred;
- model artifacts are trusted inputs only;
- no public production deployment is included;
- no rate limiting, account lockout, or real provider webhook signatures yet.

## Monetization Model

The commercial model is prepaid usage credits.

| Element | MVP rule |
| --- | --- |
| Unit of value | Credit |
| Prediction price | `1` credit per successful prediction |
| Failed prediction | Not charged |
| Top-up flow | Mock payment creates purchased credits |
| Promo mechanic | Admin-created fixed-credit promo codes |
| Ledger | Every credit/debit writes a billing transaction |

The implemented payment API stores `credits_purchased` and `amount_cents`
directly. A future commercial version can add a managed credit package catalog,
but the MVP already supports the core accounting needed for pay-per-use
predictions.

## Suggested Credit Packages

These packages are product proposals, not hardcoded MVP behavior.

| Package | Credits | Example price | Effective price per prediction |
| --- | ---: | ---: | ---: |
| Starter | 10 | USD 5.00 | USD 0.50 |
| Team | 100 | USD 45.00 | USD 0.45 |
| Growth | 500 | USD 200.00 | USD 0.40 |

Since one successful prediction costs one credit, the package price maps
directly to the per-prediction gross revenue.

## Promo Strategy

The MVP implements fixed-credit promo codes as the marketing mechanic.

Example campaigns:

| Campaign | Promo idea | Goal |
| --- | --- | --- |
| First activation | `WELCOME10` grants 10 credits | Let new users run their first predictions |
| Course cohort | Limited code for a student group | Support educational rollout |
| Retention | Bonus credits for inactive users | Encourage return usage |
| Pilot program | Larger one-time code for a team | Support customer discovery |

Controls already supported:

- active/inactive status;
- optional start and expiration dates;
- maximum redemption count;
- one redemption per user per promo code.

## Basic Financial Model

The MVP economics can be evaluated with simple formulas:

```text
revenue_per_prediction = credit_price
gross_margin_per_prediction = credit_price - variable_compute_cost - allocated_payment_fee
monthly_gross_margin = successful_predictions * gross_margin_per_prediction
break_even_predictions = monthly_fixed_cost / gross_margin_per_prediction
```

Illustrative example using the Starter package:

| Metric | Example |
| --- | ---: |
| Credit price | USD 0.50 |
| Prediction price | 1 credit |
| Revenue per successful prediction | USD 0.50 |
| Estimated variable compute cost | USD 0.05 |
| Estimated allocated payment fee | USD 0.03 |
| Gross margin per successful prediction | USD 0.42 |
| Monthly fixed cost assumption | USD 500 |
| Break-even volume | About 1,191 successful predictions/month |

This is a planning model only. Real costs depend on model size, worker runtime,
cloud provider, storage, payment provider fees, support, and traffic pattern.

## Cost Drivers

| Cost area | Driver |
| --- | --- |
| Compute | Backend and worker runtime, especially slow models |
| Database | User data, prediction tasks, billing ledger, dashboards |
| Queue | Redis broker/result backend traffic |
| Storage | Uploaded model artifacts and retained outputs |
| Monitoring | Metrics retention and Grafana/Prometheus resources |
| Payments | Provider transaction fees in a real integration |
| Support | User onboarding, debugging model uploads, billing questions |
| Security | Secrets management, sandboxing, rate limiting, audits |

## Key Metrics

Product metrics:

- registered users;
- activated users with at least one uploaded model;
- users with at least one successful prediction;
- successful prediction count;
- prediction failure rate;
- credit top-up conversion;
- promo code redemption rate;
- dashboard active users.

Business metrics:

- credits purchased;
- credits spent;
- average revenue per paying user;
- gross margin per prediction;
- retention by cohort;
- support cost per active user.

Operational metrics:

- API request count and error rate;
- prediction task status counts;
- worker success/failure counts;
- total available credits;
- payment and promo redemption counts.

## Go-To-Market

Recommended MVP path:

1. Use the project as a production-like educational demo.
2. Run pilot scenarios with trusted Scikit-learn models.
3. Use promo codes to give initial credits to test users.
4. Measure activation: registration to model upload to first prediction.
5. Validate willingness to pay with mock package prices before integrating a
   real payment provider.

## Roadmap To Commercial Readiness

Before selling to external customers, the service should add:

- real payment provider integration and signed webhook validation;
- credit package catalog;
- model execution sandboxing for untrusted uploads;
- rate limiting and login throttling;
- production secret management;
- HTTPS and production deployment workflow;
- admin panel for users, payments, models, and promo campaigns;
- worker scaling and queue visibility;
- backup and restore strategy.

## Risks

| Risk | Mitigation |
| --- | --- |
| Untrusted pickle/joblib uploads | Add sandboxed validation/execution or safer artifact format |
| Duplicate billing events | Keep idempotency keys and database constraints |
| Failed predictions harming trust | Do not charge failed predictions; expose error status clearly |
| Weak production configuration | Fail startup on unsafe non-local settings |
| Payment disputes | Add real provider records, webhooks, refunds, and audit trails |
| Cost overruns from slow models | Add per-model runtime limits and pricing tiers |

## Acceptance Alignment

This business plan matches the implemented system:

- monetization uses credits;
- prediction price is one credit per successful prediction;
- top-ups are represented by mock payments;
- promo codes grant fixed bonus credits;
- billing history is preserved through ledger rows;
- dashboard and monitoring expose usage and operational metrics.
