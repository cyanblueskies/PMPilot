"""FR-A1 — dataset upload.

Thin by design: validate, call the service, serialise. No business logic here
(.claude/rules/architecture.md).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_session
from app.models.project import (
    INGEST_FAILED,
    INGEST_PROCESSING,
    INGEST_READY,
    Project,
)
from app.schemas.dataset import ProjectStatus, UploadAccepted
from app.services.analytics import run_analysis
from app.services.ingestion import (
    MAX_FILE_BYTES,
    IngestResult,
    MissingRequiredFields,
    UploadRejected,
    ingest,
)
from app.services.ingestion.persistence import persist

router = APIRouter(tags=["datasets"])


def _persist_in_background(project_id: int, result: IngestResult) -> None:
    """Write rows, then compute KPIs and detect anomalies.

    Opens its own session: the request-scoped one is closed by the time this
    runs. Any failure is recorded on the project rather than raised into a
    void, so a client polling status learns what happened.

    Analysis runs here rather than lazily on first dashboard request so that
    `kpi_snapshots` and `anomalies` are always written. They are Must-tier
    evaluation instrumentation, not a cache, and a lazily-populated table is one
    that can quietly end up empty (.claude/rules/data-model.md).
    """
    session = SessionLocal()
    try:
        project = session.get(Project, project_id)
        if project is None:
            return
        try:
            count = persist(session, project, result)
            project.issue_count = count
            session.flush()

            run_analysis(session, project_id)
            project.ingest_status = INGEST_READY
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            project = session.get(Project, project_id)
            if project is not None:
                project.ingest_status = INGEST_FAILED
                project.ingest_error = f"{type(exc).__name__}: {exc}"
        session.commit()
    finally:
        session.close()


@router.post(
    "/datasets/upload",
    response_model=UploadAccepted,
    status_code=202,
    summary="Upload a Jira-style CSV or XLSX export",
)
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> UploadAccepted:
    content = await file.read()

    # Parsing is synchronous even though persistence is not: a rejected file
    # must fail now, with a reason, rather than surfacing later as a failed
    # background job the user has to go looking for.
    try:
        result = ingest(content, file.filename or "upload.csv")
    except MissingRequiredFields as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    project = Project(
        name=(file.filename or "Untitled").rsplit(".", 1)[0],
        source_filename=file.filename,
        ingest_status=INGEST_PROCESSING,
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    background_tasks.add_task(_persist_in_background, project.id, result)

    return UploadAccepted(
        project_id=project.id,
        name=project.name,
        status=project.ingest_status,
        row_count=result.row_count,
        dropped_rows=result.dropped_rows,
        unmapped_columns=result.mapping.unmapped_columns,
        missing_optional_fields=result.mapping.missing_optional,
        degraded_kpis=result.mapping.degraded_kpis,
        unparsed_values=result.unparsed,
    )


@router.get(
    "/projects/{project_id}",
    response_model=ProjectStatus,
    summary="Poll ingestion status",
)
def get_project(
    project_id: int, session: Session = Depends(get_session)
) -> ProjectStatus:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectStatus(
        project_id=project.id,
        name=project.name,
        status=project.ingest_status,
        issue_count=project.issue_count,
        error=project.ingest_error,
        created_at=project.created_at,
    )


@router.get("/projects", response_model=list[ProjectStatus], summary="List projects")
def list_projects(session: Session = Depends(get_session)) -> list[ProjectStatus]:
    projects = session.scalars(
        select(Project).order_by(Project.created_at.desc())
    ).all()
    return [
        ProjectStatus(
            project_id=p.id,
            name=p.name,
            status=p.ingest_status,
            issue_count=p.issue_count,
            error=p.ingest_error,
            created_at=p.created_at,
        )
        for p in projects
    ]
