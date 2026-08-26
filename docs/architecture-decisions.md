# Architecture Decisions

These decisions are taken from the project brief and implementation plan. They
are treated as agreed decisions until the owner explicitly approves a change.

| Area | Decision |
| --- | --- |
| Backend | FastAPI |
| Async processing | Celery + Redis |
| Database | PostgreSQL |
| ML | Scikit-learn |
| Model storage | Local Docker volume for MVP |
| Billing | Credit balance |
| Marketing mechanic | Promo codes |
| Promo credits | Fixed credits added to the common user balance |
| Prediction price | Fixed global price, `1` credit per successful prediction |
| Payments | Mock/sandbox payments for MVP |
| Credit packages | Deferred; payments store purchased credits directly for now |
| Roles | user and admin |
| Logout | Stateless JWT logout; client discards the bearer token |
| User analytics dashboard | Streamlit |
| Containers | Docker and Docker Compose |
| Monitoring | Prometheus and Grafana |
| Testing target | Unit and integration tests, coverage greater than 70% |
| Business model | Prepaid credits with `1` credit per successful prediction |
| Project target | Production-like educational MVP |

## Decisions Deferred

The following items are intentionally deferred until the stage where they become
implementation blockers:

- prediction result storage format;
- admin capabilities;
- CI/CD scope;
- worker scaling strategy.

The project owner remains the approval gate for these decisions.
