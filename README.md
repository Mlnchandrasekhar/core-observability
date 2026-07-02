# core-observability
SRE Zero to Hero
# Task Manager — Observability Demo App

A small, real Task Manager app (FastAPI + Postgres + vanilla JS frontend),
built specifically as a target for **Phase 3 (Weeks 15–18): Observability + SRE**.
The app itself is fully instrumented. Dashboards, alert rules, SLOs, and
runbooks are intentionally left for you to build on top — that's the actual
Week 15–18 exercise.

## Stack

- **Frontend:** plain HTML/CSS/JS, no build step, no framework
- **Backend:** FastAPI (async), SQLAlchemy 2.0 async + asyncpg
- **DB:** PostgreSQL
- **Instrumentation:** `prometheus-client`, `structlog`, OpenTelemetry SDK

## What's already instrumented

### Metrics (`/metrics`, Prometheus text format)
- `http_requests_total{method,path,status}` — RED: requests + errors
- `http_request_duration_seconds{method,path}` (histogram) — RED: duration
- `http_requests_in_progress{method,path}` (gauge) — in-flight requests
- `db_pool_size`, `db_pool_checked_out_connections` — USE: DB saturation
- `db_query_duration_seconds{operation}` — per-query-type latency
- Business metrics: `tasks_created_total`, `tasks_completed_total`,
  `tasks_deleted_total`, `tasks_active` (gauge)
- Path labels are normalized (`/tasks/42` → `/tasks/{id}`) so cardinality
  doesn't explode — extend `normalize_path()` in `app/metrics.py` if you add
  more parameterized routes.

### Logs (structlog, JSON only, to stdout)
- Every line includes: `request_id`, `service`, `level`, `timestamp` (ISO8601),
  plus `trace_id`/`span_id` when a span is active, and `duration_ms` on the
  per-request completion log.
- `request_id` is bound via `ObservabilityMiddleware` using
  `structlog.contextvars` — bound once per request, cleared after, so it
  automatically appears on every log line emitted anywhere during that
  request without threading it through function signatures.
- A denylist scrubs common sensitive keys (`password`, `token`, `authorization`,
  etc.) if they ever end up in log kwargs.

### Traces (OpenTelemetry SDK → OTLP gRPC → Tempo)
- Auto-instrumentation: FastAPI (HTTP server spans, and it automatically
  reads/writes the W3C `traceparent` header for propagation) + SQLAlchemy +
  asyncpg (DB client spans).
- Manual spans in `app/routers/tasks.py` (`create_task`, `list_tasks`, etc.)
  add business-level span names/attributes around the auto-generated DB spans.
- `trace_id`/`span_id` are injected into every log line (see `tracing.py` +
  `logging_config.py`), which is what makes the metrics → logs → traces
  correlation workflow from Week 16 actually work end-to-end.
- Exporter endpoint is env-configurable (`OTEL_EXPORTER_OTLP_ENDPOINT`) so you
  can point it at Tempo directly, or at an Alloy/OTel-collector in front of it.

### Fault injection (`/debug/*`, dev only)
- `GET /debug/slow?seconds=3` — simulate latency for SLO burn-rate testing
- `GET /debug/error?rate=1.0` — simulate 500s for error-rate alert testing
- `GET /debug/cpu?seconds=2` — simulate CPU saturation
- The frontend has buttons for these under "Incident simulation" — useful for
  Week 17's "break your app 3 ways" exercise.

## Running it

```bash
cp backend/.env.example backend/.env   # then edit OTEL_EXPORTER_OTLP_ENDPOINT etc.
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend: http://localhost:8000 (docs at `/docs`, metrics at `/metrics`)
- Postgres: localhost:5432 (`taskuser` / `taskpass` / `taskdb`)

By default `OTEL_EXPORTER_OTLP_ENDPOINT` points at
`http://host.docker.internal:4317`, assuming your LGTM stack runs on the host
or is reachable there. Change it to wherever your Tempo/Alloy OTLP receiver
actually listens.

## What's deliberately left for you (this is the Phase 3 work)

- Prometheus scrape config / ServiceMonitor for `/metrics`
- Grafana dashboards (RED for this service, USE for its resources) as
  Git-committed JSON ConfigMaps
- Alertmanager rules: high error rate, p99 latency SLO breach, DB pool
  saturation, GPU rules (n/a here, but pattern's the same)
- Promtail/Alloy log collection config for the JSON stdout logs → Loki, with
  labels on `namespace`/`pod`/`app` (not on high-cardinality fields like
  `request_id` — keep those in the log body, query them via LogQL filters)
- Loki alerting on log patterns (e.g. burst of `level=error`)
- SLI/SLO definitions and PromQL error-budget/burn-rate expressions
- The 5 runbooks + incident simulation + blameless postmortem
- DCGM/GPU dashboards (not applicable to this app, but same pattern applies
  when you bring in a GPU workload in Phase 6)

## Project layout

```
observability-demo/
├── backend/
│   ├── app/
│   │   ├── config.py          # env-driven settings
│   │   ├── logging_config.py  # structlog JSON setup
│   │   ├── metrics.py         # all Prometheus collectors
│   │   ├── middleware.py      # request_id + RED metrics + access log
│   │   ├── tracing.py         # OTel SDK setup, auto + manual spans
│   │   ├── db.py               # async SQLAlchemy engine/session
│   │   ├── models.py           # Task ORM model
│   │   ├── schemas.py          # Pydantic I/O schemas
│   │   ├── routers/
│   │   │   ├── tasks.py        # CRUD, instrumented
│   │   │   ├── health.py       # liveness/readiness
│   │   │   └── debug.py        # fault injection for incident drills
│   │   └── main.py             # app wiring, /metrics endpoint
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── docker-compose.yml
```