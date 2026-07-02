"""
Structured JSON logging with structlog.

Requirements this satisfies (Phase 3 / Week 16, Monday):
  - JSON logs only.
  - Always include: request_id, service, level, timestamp (ISO8601), duration_ms.
  - Never log sensitive data (see `_scrub_sensitive_keys`).
  - request_id is bound via FastAPI middleware using contextvars (see middleware.py).

We also bind `trace_id` / `span_id` (when a span is active) so every log line
can be pivoted straight into Tempo from Grafana/Loki -- this is what makes
the metrics -> logs -> traces correlation workflow (Week 16, Thursday) work.
"""
import logging
import sys

import structlog
from opentelemetry import trace

from app.config import settings

# Context that request_id (and anything else per-request) gets bound into.
# Cleared/reset by the middleware on every request.
contextvars_processor = structlog.contextvars.merge_contextvars

# Keys we NEVER want to accidentally log even if a caller passes them in
# (e.g. `log.info("login", password=pw)` should never happen, but belt & suspenders).
_SENSITIVE_KEYS = {
    "password", "passwd", "secret", "token", "authorization", "auth",
    "api_key", "apikey", "access_token", "refresh_token", "credit_card",
    "ssn", "cookie", "set-cookie",
}


def _scrub_sensitive_keys(_logger, _method_name, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def _add_trace_context(_logger, _method_name, event_dict):
    """Attach active OTel trace_id/span_id to the log line, if any."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL.upper(),
    )

    structlog.configure(
        processors=[
            contextvars_processor,               # pulls in request_id etc. bound per-request
            structlog.stdlib.add_log_level,       # -> "level"
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),  # -> "timestamp", ISO8601
            _add_trace_context,                   # -> trace_id / span_id
            _scrub_sensitive_keys,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),  # JSON logs only
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_context):
    """
    Every logger is bound with `service` so every line is self-identifying
    once it lands in Loki (label by `service`, filter by content).
    """
    return structlog.get_logger().bind(
        service=settings.SERVICE_NAME,
        environment=settings.ENVIRONMENT,
        **initial_context,
    )
EOF
echo done