"""
Liveness/readiness endpoints. Split on purpose:
  - /health/live  -> process is up (for K8s livenessProbe)
  - /health/ready -> process AND its dependencies (DB) are reachable (readinessProbe)
This distinction matters for the runbooks you'll write in Week 17 (e.g. "pod is
Running but not Ready" -> check /health/ready first).
"""
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(tags=["health"])
log = structlog.get_logger()


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "reachable"}
    except Exception:
        log.exception("readiness_check_failed")
        return {"status": "degraded", "db": "unreachable"}