# Monitoring

Step 12 adds local Prometheus and Grafana monitoring.

## Metrics Endpoint

The backend exposes Prometheus-compatible metrics at:

```text
http://127.0.0.1:18000/metrics
```

The endpoint includes:

- HTTP request counts by method, path, and status code.
- HTTP error counts for 4xx and 5xx responses.
- HTTP request duration summary samples.
- Prediction task counts by status.
- Completed worker prediction counts by status.
- Billing transaction counts and credit totals.
- Total available credits.
- Uploaded model counts.
- Payment counts.
- Promo redemption count.

## Local Services

When Docker Compose starts the stack, Prometheus scrapes the backend every five
seconds and Grafana provisions a Prometheus datasource plus an MVP dashboard.

| Service | URL |
| --- | --- |
| Prometheus | `http://127.0.0.1:19090` |
| Grafana | `http://127.0.0.1:13000` |

Default admin logins for local development:

| UI | Login | Password |
| --- | --- | --- |
| Grafana | `admin` | `admin` |
| Application dashboard | `admin` | `admin` |

## Manual Check

1. Start the local stack.
2. Open `/metrics` and verify the text response contains `ml_http_requests_total`.
3. Open Prometheus and query `ml_prediction_tasks`.
4. Open Grafana and check the `ML Prediction Service` dashboard.
