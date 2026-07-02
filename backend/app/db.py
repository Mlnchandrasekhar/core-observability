"""
Async SQLAlchemy engine/session + a helper to publish pool stats to Prometheus
(the USE "saturation" signal for the DB resource).
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.metrics import DB_POOL_CHECKED_OUT, DB_POOL_SIZE

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def publish_pool_metrics() -> None:
    """Call periodically (see main.py startup task) to keep db_pool_size /
    db_pool_checked_out_connections gauges fresh for Grafana."""
    pool = engine.pool
    DB_POOL_SIZE.set(settings.DB_POOL_SIZE)
    try:
        DB_POOL_CHECKED_OUT.set(pool.checkedout())
    except NotImplementedError:
        # Some pool implementations (e.g. NullPool in tests) don't support this.
        pass


async def init_models() -> None:
    """Dev/demo convenience: create tables if they don't exist.
    In a real environment you'd use Alembic migrations instead."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)