"""
Fault-injection endpoints -- deliberately break the app on demand so you can
drive Week 17 ("Incident simulation. Break your app 3 ways.") and test that
your alert rules actually fire and your runbooks actually work.

DO NOT expose this router outside dev/test environments.
"""
import asyncio
import random
import time

import structlog
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/debug", tags=["debug"])
log = structlog.get_logger()


@router.get("/slow")
async def slow(seconds: float = 3.0):
    """Simulate a slow downstream call -> use to test p99 latency SLO burn alerts."""
    log.warning("debug_slow_endpoint_triggered", delay_seconds=seconds)
    await asyncio.sleep(seconds)
    return {"slept_seconds": seconds}


@router.get("/error")
async def error(rate: float = 1.0):
    """Simulate error responses -> use to test high error-rate alerts.
    `rate` is the probability (0-1) of returning a 500."""
    if random.random() < rate:
        log.error("debug_error_endpoint_triggered", rate=rate)
        raise HTTPException(status_code=500, detail="Simulated failure")
    return {"status": "ok (no error this time)"}


@router.get("/cpu")
async def cpu_spike(seconds: float = 2.0):
    """Simulate CPU saturation -> use to test resource/saturation alerts."""
    log.warning("debug_cpu_spike_triggered", seconds=seconds)
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass  # busy loop, deliberately blocking
    return {"busy_seconds": seconds}