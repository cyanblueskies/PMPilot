"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Decision support for agile projects: deterministic KPI and anomaly "
        "analysis, with grounded LLM narration over the computed results."
    ),
    version="0.1.0",
)

app.include_router(health_router, prefix="/api")
