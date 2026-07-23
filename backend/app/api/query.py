"""FR-D1 / FR-F1 / FR-F2 — natural language query over structured fields.

Thin by design: validate, call the service, serialise
(.claude/rules/architecture.md).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.project import INGEST_READY, Project
from app.schemas.report import QueryEvidence, QueryRequest, QueryResponse
from app.services.nl2sql import SUPPORTED_QUESTIONS, answer_question

router = APIRouter(tags=["query"])


@router.get(
    "/query/supported",
    summary="The question types FR-D1 answers",
)
def supported_questions() -> list[dict]:
    """Published so a user can see the boundary rather than discover it by
    being refused, and so the >80% accuracy target has a stated scope.
    """
    return [
        {"key": q.key, "description": q.description, "example": q.example}
        for q in SUPPORTED_QUESTIONS
    ]


@router.post(
    "/projects/{project_id}/query",
    response_model=QueryResponse,
    summary="Ask a question about a project",
)
def ask(
    project_id: int,
    request: QueryRequest,
    session: Session = Depends(get_session),
) -> QueryResponse:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.ingest_status != INGEST_READY:
        raise HTTPException(
            status_code=409,
            detail=f"Project is not ready (status: {project.ingest_status}).",
        )

    outcome = answer_question(session, project_id, request.question)

    # Committed whether or not the question was answerable: the query_logs rows
    # written along the way are the experiment's data, and a refused or failed
    # call is as much evidence as a successful one.
    session.commit()

    evidence = None
    if outcome.result is not None:
        evidence = QueryEvidence(
            generated_sql=outcome.result.sql,
            row_count=outcome.result.row_count,
            rows=outcome.result.rows,
        )

    # An out-of-scope question is answered, not errored: refusing is the
    # designed behaviour (.claude/rules/scope.md -> FR-D1), and a 4xx would
    # make the client treat a correct outcome as a fault.
    return QueryResponse(
        question=outcome.question,
        answer=outcome.answer,
        in_scope=outcome.in_scope,
        evidence=evidence,
        query_log_id=outcome.query_log_id,
        refusal_reason=outcome.refusal_reason,
    )
