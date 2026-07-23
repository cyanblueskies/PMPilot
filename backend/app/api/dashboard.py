"""FR-E1 / FR-E2 / FR-E3 — dashboard and anomaly views.

These must respond with the LLM entirely unavailable: the generative track is
an enhancement over a system that is already useful without it
(.claude/rules/architecture.md). Nothing in this module imports it.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.analytics import Anomaly
from app.models.project import INGEST_READY, Project, Sprint
from app.services.analytics import load_project_frame
from app.services.analytics.pipeline import analyse

router = APIRouter(tags=["dashboard"])


def _ready_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.ingest_status != INGEST_READY:
        # 409 rather than 404: the project exists, it just is not analysable
        # yet. A client polling status can distinguish the two.
        raise HTTPException(
            status_code=409,
            detail=f"Project is not ready (status: {project.ingest_status}).",
        )
    return project


@router.get(
    "/projects/{project_id}/dashboard",
    summary="KPIs, burndown series and anomalies for a project",
)
def get_dashboard(
    project_id: int,
    include_series: bool = Query(
        True, description="Include per-day burndown points"
    ),
    session: Session = Depends(get_session),
) -> dict:
    project = _ready_project(session, project_id)

    frame = load_project_frame(session, project_id)
    analysis = analyse(frame, project_id=project_id, project_name=project.name)

    return analysis.to_dict(include_series=include_series)


@router.get(
    "/projects/{project_id}/anomalies",
    summary="Detected anomalies, most severe first",
)
def get_anomalies(
    project_id: int,
    anomaly_type: str | None = Query(None, description="Filter by anomaly type"),
    session: Session = Depends(get_session),
) -> list[dict]:
    _ready_project(session, project_id)

    # Read from the stored rows rather than recomputing: these are the records
    # the FR-A4 ground-truth comparison scores against, so the view and the
    # evaluation must be looking at the same thing.
    statement = (
        select(Anomaly, Sprint.name, Sprint.sequence)
        .outerjoin(Sprint, Anomaly.sprint_id == Sprint.id)
        .where(Anomaly.project_id == project_id)
    )
    if anomaly_type:
        statement = statement.where(Anomaly.anomaly_type == anomaly_type)

    rows = session.execute(statement).all()
    rows.sort(key=lambda r: (-(r[0].severity or 0.0), r[2] if r[2] is not None else 0))

    return [
        {
            "id": anomaly.id,
            "sprint": sprint_name,
            "sprint_sequence": sequence,
            "anomaly_type": anomaly.anomaly_type,
            "severity": anomaly.severity,
            "detail": anomaly.detail,
            "detected_at": anomaly.detected_at.isoformat(),
        }
        for anomaly, sprint_name, sequence in rows
    ]
