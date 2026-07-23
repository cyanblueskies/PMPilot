"""FR-F3 / FR-F4 — executive summary generation, retrieval and export.

Generation runs through BackgroundTasks: it makes two LLM calls and would
otherwise hold the request open for tens of seconds
(.claude/rules/data-model.md).
"""

from __future__ import annotations

import io

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_session
from app.models.llm import Report
from app.models.project import INGEST_READY, Project
from app.schemas.report import ReportOut, ReportRequested, ReportSummary
from app.services.analytics import load_project_frame
from app.services.analytics.pipeline import analyse
from app.services.llm.strategies import GROUNDED, NAIVE
from app.services.llm.summary import generate_narrative

router = APIRouter(tags=["reports"])

PENDING_MARKER = "_Generating…_"


def _ready_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.ingest_status != INGEST_READY:
        raise HTTPException(
            status_code=409,
            detail=f"Project is not ready (status: {project.ingest_status}).",
        )
    return project


def _generate_in_background(report_id: int, project_id: int, strategy: str) -> None:
    session = SessionLocal()
    try:
        report = session.get(Report, report_id)
        if report is None:
            return
        try:
            project = session.get(Project, project_id)
            frame = load_project_frame(session, project_id)
            analysis = analyse(
                frame, project_id=project_id, project_name=project.name if project else ""
            )

            narrative = generate_narrative(
                session, analysis, frame, strategy_name=strategy
            )

            if narrative.ok:
                report.content = (
                    f"## Summary\n\n{narrative.summary.text.strip()}\n\n"
                    f"## Recommended actions\n\n{narrative.recommendations.text.strip()}\n"
                )
            else:
                # The failure is recorded in the report itself rather than left
                # as a silently empty document; query_logs already holds the
                # error detail for the evaluation.
                reason = narrative.summary.error or narrative.recommendations.error
                report.content = (
                    "The narrative could not be generated.\n\n"
                    f"Reason: {reason}\n\n"
                    "The dashboard and anomaly views are unaffected — they do "
                    "not depend on the language model."
                )

            report.query_log_id = narrative.summary.query_log_id
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            report = session.get(Report, report_id)
            if report is not None:
                report.content = f"Report generation failed: {type(exc).__name__}: {exc}"
        session.commit()
    finally:
        session.close()


@router.post(
    "/projects/{project_id}/report/generate",
    response_model=ReportRequested,
    status_code=202,
    summary="Generate an executive summary and recommendations",
)
def generate_report(
    project_id: int,
    background_tasks: BackgroundTasks,
    strategy: str = Query(
        GROUNDED,
        description=(
            "Prompting strategy. 'grounded' sends only computed metrics; "
            "'naive' sends raw issue rows and exists as the FR-D5 experimental "
            "baseline."
        ),
    ),
    session: Session = Depends(get_session),
) -> ReportRequested:
    project = _ready_project(session, project_id)

    if strategy not in (GROUNDED, NAIVE):
        raise HTTPException(
            status_code=422, detail=f"Unknown strategy '{strategy}'."
        )

    report = Report(
        project_id=project_id,
        title=f"{project.name} — status report",
        content=PENDING_MARKER,
        prompting_strategy=strategy,
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    background_tasks.add_task(_generate_in_background, report.id, project_id, strategy)

    return ReportRequested(
        report_id=report.id,
        project_id=project_id,
        status="generating",
        prompting_strategy=strategy,
    )


@router.get(
    "/projects/{project_id}/reports",
    response_model=list[ReportSummary],
    summary="List a project's reports",
)
def list_reports(
    project_id: int, session: Session = Depends(get_session)
) -> list[ReportSummary]:
    reports = session.scalars(
        select(Report)
        .where(Report.project_id == project_id)
        .order_by(Report.created_at.desc())
    ).all()
    return [
        ReportSummary(
            report_id=r.id,
            title=r.title,
            prompting_strategy=r.prompting_strategy,
            created_at=r.created_at,
        )
        for r in reports
    ]


def _load_report(session: Session, project_id: int, report_id: int) -> Report:
    report = session.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get(
    "/projects/{project_id}/report/{report_id}",
    response_model=ReportOut,
    summary="Fetch a generated report",
)
def get_report(
    project_id: int, report_id: int, session: Session = Depends(get_session)
) -> ReportOut:
    report = _load_report(session, project_id, report_id)
    return ReportOut(
        report_id=report.id,
        project_id=report.project_id,
        title=report.title,
        content=report.content,
        prompting_strategy=report.prompting_strategy,
        created_at=report.created_at,
        query_log_id=report.query_log_id,
    )


@router.get(
    "/projects/{project_id}/report/{report_id}/export",
    summary="Download a report as Markdown",
)
def export_report(
    project_id: int, report_id: int, session: Session = Depends(get_session)
) -> StreamingResponse:
    report = _load_report(session, project_id, report_id)

    document = (
        f"# {report.title}\n\n"
        f"Generated: {report.created_at.isoformat()}\n"
        f"Prompting strategy: {report.prompting_strategy}\n\n"
        f"{report.content}"
    )
    filename = f"pmpilot-report-{report.id}.md"

    return StreamingResponse(
        io.BytesIO(document.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
