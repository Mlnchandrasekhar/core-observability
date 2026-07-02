"""
Task CRUD endpoints -- the actual "app" being observed.

Every handler:
  - logs at least one structured event with business context (never raw SQL/PII)
  - wraps its DB call in a manual OTel span with useful attributes
  - updates DB_QUERY_DURATION_SECONDS and the business counters/gauges

Auto-instrumentation (FastAPI + SQLAlchemy) already gives you HTTP server spans
and DB client spans "for free" -- the manual spans below add business-meaning
around them (e.g. "why" a query ran, not just "a query ran").
"""
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.metrics import (
    DB_QUERY_DURATION_SECONDS,
    TASKS_ACTIVE,
    TASKS_COMPLETED_TOTAL,
    TASKS_CREATED_TOTAL,
    TASKS_DELETED_TOTAL,
)
from app.models import Task
from app.schemas import TaskCreate, TaskOut, TaskUpdate
from app.tracing import get_tracer

router = APIRouter(prefix="/tasks", tags=["tasks"])
log = structlog.get_logger()
tracer = get_tracer(__name__)


async def _refresh_active_gauge(db: AsyncSession) -> None:
    result = await db.execute(select(func.count()).select_from(Task).where(Task.completed.is_(False)))
    TASKS_ACTIVE.set(result.scalar_one())


@router.get("", response_model=list[TaskOut])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("list_tasks") as span:
        start = time.perf_counter()
        result = await db.execute(select(Task).order_by(Task.created_at.desc()))
        tasks = result.scalars().all()
        DB_QUERY_DURATION_SECONDS.labels(operation="select_all_tasks").observe(
            time.perf_counter() - start
        )
        span.set_attribute("tasks.count", len(tasks))
        log.info("tasks_listed", count=len(tasks))
        return tasks


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("create_task") as span:
        span.set_attribute("task.title_length", len(payload.title))

        task = Task(title=payload.title, description=payload.description)
        db.add(task)

        start = time.perf_counter()
        await db.commit()
        DB_QUERY_DURATION_SECONDS.labels(operation="insert_task").observe(
            time.perf_counter() - start
        )
        await db.refresh(task)

        TASKS_CREATED_TOTAL.inc()
        await _refresh_active_gauge(db)

        span.set_attribute("task.id", task.id)
        log.info("task_created", task_id=task.id)
        return task


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("get_task") as span:
        span.set_attribute("task.id", task_id)
        task = await db.get(Task, task_id)
        if task is None:
            log.warning("task_not_found", task_id=task_id)
            raise HTTPException(status_code=404, detail="Task not found")
        return task


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: int, payload: TaskUpdate, db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("update_task") as span:
        span.set_attribute("task.id", task_id)
        task = await db.get(Task, task_id)
        if task is None:
            log.warning("task_not_found", task_id=task_id)
            raise HTTPException(status_code=404, detail="Task not found")

        was_completed = task.completed
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)

        start = time.perf_counter()
        await db.commit()
        DB_QUERY_DURATION_SECONDS.labels(operation="update_task").observe(
            time.perf_counter() - start
        )
        await db.refresh(task)

        if task.completed and not was_completed:
            TASKS_COMPLETED_TOTAL.inc()
        await _refresh_active_gauge(db)

        log.info("task_updated", task_id=task_id, fields=list(update_data.keys()))
        return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    with tracer.start_as_current_span("delete_task") as span:
        span.set_attribute("task.id", task_id)
        task = await db.get(Task, task_id)
        if task is None:
            log.warning("task_not_found", task_id=task_id)
            raise HTTPException(status_code=404, detail="Task not found")

        start = time.perf_counter()
        await db.delete(task)
        await db.commit()
        DB_QUERY_DURATION_SECONDS.labels(operation="delete_task").observe(
            time.perf_counter() - start
        )

        TASKS_DELETED_TOTAL.inc()
        await _refresh_active_gauge(db)

        log.info("task_deleted", task_id=task_id)