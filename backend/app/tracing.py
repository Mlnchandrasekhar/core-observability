"""
OpenTelemetry setup: auto-instrumentation + manual spans, exported to Tempo.
"""

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from app.config import settings

logging.basicConfig(level=logging.DEBUG)

_tracer_provider: TracerProvider | None = None


def configure_tracing() -> None:
    """
    Call once at startup before serving traffic.
    """
    global _tracer_provider

    if not settings.OTEL_ENABLED:
        print("OTEL disabled")
        return

    print("=== CONFIGURING OPENTELEMETRY ===")
    print(f"OTLP endpoint: {settings.OTEL_EXPORTER_OTLP_ENDPOINT}")
    print(f"Service name: {settings.SERVICE_NAME}")

    resource = Resource.create(
        {
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    sampler = ParentBased(
        TraceIdRatioBased(
            settings.OTEL_TRACES_SAMPLER_RATIO
        )
    )

    _tracer_provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )

    try:
        exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,
        )

        print("OTLP exporter created successfully")

        # Export to Alloy/Tempo
        _tracer_provider.add_span_processor(
            BatchSpanProcessor(exporter)
        )

        # Print spans to pod logs for debugging
        _tracer_provider.add_span_processor(
            SimpleSpanProcessor(
                ConsoleSpanExporter()
            )
        )

        trace.set_tracer_provider(_tracer_provider)

        SQLAlchemyInstrumentor().instrument(
            tracer_provider=_tracer_provider
        )

        AsyncPGInstrumentor().instrument(
            tracer_provider=_tracer_provider
        )

        print("OpenTelemetry configured successfully")

    except Exception as e:
        print(f"FAILED TO CONFIGURE OTEL: {e}")
        raise


def instrument_app(app) -> None:
    """
    Instrument FastAPI application.
    """
    if not settings.OTEL_ENABLED:
        return

    print("Instrumenting FastAPI app")

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider,
    )

    print("FastAPI instrumentation completed")


def shutdown_tracing() -> None:
    global _tracer_provider

    if _tracer_provider is not None:
        print("Flushing traces...")
        _tracer_provider.force_flush()
        _tracer_provider.shutdown()


def get_tracer(name: str = "taskmanager.manual"):
    return trace.get_tracer(name)