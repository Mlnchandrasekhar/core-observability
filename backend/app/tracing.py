"""
OpenTelemetry setup: auto-instrumentation + manual spans, exported to Tempo.

- Auto-instrumentation: FastAPI (HTTP server spans) + SQLAlchemy (DB client spans)
  via OTel's instrumentor packages -- zero code changes needed in routers for these.
- Manual spans: use `tracer.start_as_current_span(...)` in business logic where a
  span boundary isn't implied by a library call (see routers/tasks.py).
- Context propagation: OTel's FastAPI instrumentation automatically reads/writes
  the W3C `traceparent` header on incoming/outgoing requests, so if this service
  calls another instrumented service, the trace continues unbroken.
"""
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from app.config import settings

_tracer_provider: TracerProvider | None = None


def configure_tracing() -> None:
    """Call once at startup, before the app starts serving traffic."""
    global _tracer_provider

    if not settings.OTEL_ENABLED:
        return

    resource = Resource.create(
        {
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    sampler = ParentBased(TraceIdRatioBased(settings.OTEL_TRACES_SAMPLER_RATIO))
    _tracer_provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_tracer_provider)

    # Auto-instrument the DB layer. Do this before engine creation isn't required,
    # but call it once at startup.
    SQLAlchemyInstrumentor().instrument(tracer_provider=_tracer_provider)
    AsyncPGInstrumentor().instrument(tracer_provider=_tracer_provider)


def instrument_app(app) -> None:
    """Auto-instrument the FastAPI app itself (HTTP server spans, traceparent
    propagation). Call after the app object exists, once at startup."""
    if not settings.OTEL_ENABLED:
        return
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider)


def shutdown_tracing() -> None:
    if _tracer_provider is not None:
        _tracer_provider.shutdown()


def get_tracer(name: str = "taskmanager.manual"):
    """Use this in business logic for manual spans, e.g.:

        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("validate-task-payload") as span:
            span.set_attribute("task.title_length", len(title))
            ...
    """
    return trace.get_tracer(name)