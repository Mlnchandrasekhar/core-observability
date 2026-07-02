"""
Request-scoped middleware:

1. Generates/propagates a request_id (accepts an inbound X-Request-ID so it
   also works behind a gateway that already assigns one), binds it into
   structlog's contextvars so EVERY log line emitted during this request
   automatically carries request_id -- no need to pass it around manually.
2. Times the request and emits one structured "request completed" log line
   with duration_ms (per the Week 16 Monday requirement).
3. Records RED metrics (count, duration, in-flight) into Prometheus.
4. Echoes the request_id back on the response header for client-side
   correlation (frontend can log it, or you can grep for it in Loki).
"""
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import (
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    normalize_path,
)

log = structlog.get_logger()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )

        path_label = normalize_path(request.url.path)
        method_label = request.method

        # Skip /metrics from generating metrics-about-metrics noise but still log it.
        track_metrics = path_label != "/metrics"

        if track_metrics:
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method_label, path=path_label).inc()

        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            log.exception("unhandled_exception")
            raise
        finally:
            duration_s = time.perf_counter() - start
            duration_ms = round(duration_s * 1000, 2)

            if track_metrics:
                HTTP_REQUESTS_IN_PROGRESS.labels(method=method_label, path=path_label).dec()
                HTTP_REQUESTS_TOTAL.labels(
                    method=method_label, path=path_label, status=str(status_code)
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=method_label, path=path_label
                ).observe(duration_s)

            log.info(
                "request_completed",
                status_code=status_code,
                duration_ms=duration_ms,
            )
            structlog.contextvars.clear_contextvars()