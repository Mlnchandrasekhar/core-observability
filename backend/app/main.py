import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_models, publish_pool_metrics
from app.logging_config import configure_logging, get_logger
from app.metrics import render_metrics
from app.middleware import ObservabilityMiddleware
from app.routers import debug, health, tasks
from app.tracing import configure_tracing, instrument_app, shutdown_tracing

configure_logging()
log = get_logger()

_pool_metrics_task: asyncio.Task | None = None


async def _pool_metrics_loop():
    while True:
        publish_pool_metrics()
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool_metrics_task
    configure_tracing()
    await init_models()
    _pool_metrics_task = asyncio.create_task(_pool_metrics_loop())
    log.info("app_startup", service=settings.SERVICE_NAME, version=settings.SERVICE_VERSION)
    yield
    if _pool_metrics_task:
        _pool_metrics_task.cancel()
    shutdown_tracing()
    log.info("app_shutdown")


app = FastAPI(
    title="Task Manager API",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(ObservabilityMiddleware)

app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(debug.router)

# OTel FastAPI auto-instrumentation: wraps every route with an HTTP server span
# and handles `traceparent` extraction/injection automatically.
instrument_app(app)


@app.get("/metrics")
async def metrics():
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@app.get("/")
async def root():
    return {"service": settings.SERVICE_NAME, "status": "ok"}