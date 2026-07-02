"""
Central app configuration.

Everything observability-related is env-driven on purpose: this same image
should run unchanged in dev/test/prod, pointed at different Tempo/Loki/
Prometheus backends per environment (as you're already doing with LGTM).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Identity ---
    SERVICE_NAME: str = "taskmanager-api"
    SERVICE_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "dev"  # dev | test | prod

    # --- Database ---
    # e.g. postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_URL: str = "postgresql+asyncpg://taskuser:taskpass@postgres:5432/taskdb"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- Tracing (OTel -> Tempo) ---
    # Point this at your Alloy/OTel-collector or directly at Tempo's OTLP gRPC receiver,
    # e.g. http://tempo:4317 or http://alloy.observability:4317
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_TRACES_SAMPLER_RATIO: float = 1.0  # 1.0 = sample everything (fine for a demo/low-traffic app)
    OTEL_ENABLED: bool = True

    # --- CORS (frontend is a separate static origin) ---
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()