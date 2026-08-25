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
| Payments | Mock/sandbox payments for MVP |
| Roles | user and admin |
| User analytics dashboard | Streamlit |
| Containers | Docker and Docker Compose |
| Monitoring | Prometheus and Grafana |
| Testing target | Unit and integration tests, coverage greater than 70% |
| Project target | Production-like educational MVP |

## Decisions Deferred

The following items are intentionally deferred until the stage where they become
implementation blockers:

- prediction price;
- credit packages;
- exact promo code rules;
- ML input contract;
- model upload limits;
- prediction result storage format;
- admin capabilities;
- CI/CD scope;
- worker scaling strategy.

The project owner remains the approval gate for these decisions.
