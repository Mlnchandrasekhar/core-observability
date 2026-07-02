"""
Prometheus instrumentation.

Exposes everything you need to build RED (Requests, Errors, Duration) dashboards
for this service, plus a couple of USE-style resource gauges and a few business
metrics. Nothing here creates dashboards/alerts -- that's your Week 15 work in
Grafana/Alertmanager. This module only makes the numbers available at /metrics.
"""
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

REGISTRY = CollectorRegistry()

# ---- RED: Requests, Errors, Duration --------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
    registry=REGISTRY,
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    labelnames=("method", "path"),
    registry=REGISTRY,
)

# ---- USE: Utilization, Saturation, Errors (resource-ish) -------------------

DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Configured SQLAlchemy connection pool size",
    registry=REGISTRY,
)

DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out_connections",
    "Connections currently checked out of the pool (saturation signal)",
    registry=REGISTRY,
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    labelnames=("operation",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

# ---- Business metrics -------------------------------------------------------

TASKS_CREATED_TOTAL = Counter(
    "tasks_created_total", "Total tasks created", registry=REGISTRY
)
TASKS_COMPLETED_TOTAL = Counter(
    "tasks_completed_total", "Total tasks marked completed", registry=REGISTRY
)
TASKS_DELETED_TOTAL = Counter(
    "tasks_deleted_total", "Total tasks deleted", registry=REGISTRY
)
TASKS_ACTIVE = Gauge(
    "tasks_active", "Current number of incomplete tasks", registry=REGISTRY
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def normalize_path(path: str) -> str:
    """
    Collapse path params (e.g. /tasks/42) into a template (/tasks/{id}) so
    labels don't explode cardinality. Extend this if you add more routes
    with path params.
    """
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        normalized.append("{id}" if part.isdigit() else part)
    return "/" + "/".join(normalized) if normalized != [""] else "/"
