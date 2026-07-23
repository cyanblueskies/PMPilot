"""Health check.

Reports database reachability separately from process liveness. The dashboard
is required to work with the LLM unavailable, so LLM status is deliberately not
part of this check — a degraded LLM must not make the service look down
(.claude/rules/architecture.md).
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "up"
    except Exception as exc:  # noqa: BLE001 - report any failure, don't crash
        database = f"down: {type(exc).__name__}"

    return {"status": "ok", "database": database}
