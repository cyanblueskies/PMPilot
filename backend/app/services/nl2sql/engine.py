"""FR-D1 — natural language to SQL, end to end.

Flow: classify -> refuse if out of scope -> generate SQL -> validate -> execute
on the read-only connection -> have the model phrase the result set as prose.

The model never sees the user's question spliced into SQL. It emits a query,
which is then parsed and validated independently before anything runs
(.claude/rules/security.md).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.llm.client import generate
from app.services.llm.strategies import GROUNDED, PromptPayload
from app.services.nl2sql.execute import QueryFailed, QueryResult, run
from app.services.nl2sql.questions import (
    SupportedQuestion,
    classify,
    out_of_scope_message,
)
from app.services.nl2sql.safety import UnsafeQuery, validate

SCHEMA_DESCRIPTION = """\
Tables available (PostgreSQL):

issues(
  id, project_id, sprint_id, issue_key, issue_type, status, assignee, reporter,
  priority, story_points (may be NULL), created_date, started_date,
  resolved_date, due_date, labels, epic_link, original_estimate, time_spent
)
sprints(id, project_id, name, start_date, end_date, sequence)
projects(id, name, issue_count, created_at)
kpi_snapshots(id, project_id, sprint_id, metric, value, detail, computed_at)
anomalies(id, project_id, sprint_id, anomaly_type, severity, detail, detected_at)

Notes:
- Completed work has status in ('Done','Closed','Resolved','Complete').
- Blocked work has status = 'Blocked'.
- story_points is NULL when an issue was never estimated. NULL is not zero.
- All timestamps are timezone-aware UTC.
- anomaly_type is one of: velocity_drop, overdue_pileup, blocked_cluster.
"""

SQL_SYSTEM = """\
You translate a question about a software project into a single PostgreSQL \
SELECT statement.

Rules:
- Output only the SQL. No explanation, no markdown fence, no trailing semicolon.
- SELECT only. Never write, alter or delete anything.
- Always filter by the project_id you are given.
- Only use the tables and columns described. Do not invent columns.
- Prefer aggregates over returning many rows; keep the result under 200 rows.
- If the question cannot be answered from these tables, output exactly: \
UNANSWERABLE\
"""

PHRASE_SYSTEM = """\
You state the answer to a question using a result set from a database query.

Rules:
- Every number you give must come from the result set. Do not compute new \
figures and do not estimate.
- If the result set is empty, say that no matching records were found.
- Answer in one or two sentences. No preamble, no restating the question.\
"""


@dataclass
class NlQueryOutcome:
    question: str
    in_scope: bool
    answer: str = ""
    refusal_reason: str | None = None
    result: QueryResult | None = None
    query_log_id: int | None = None
    matched_type: str | None = None
    metadata: dict = field(default_factory=dict)


def _strip_fence(text: str) -> str:
    """Models often wrap SQL in a fence despite being told not to."""
    cleaned = text.strip()
    match = re.search(r"```(?:sql)?\s*(.+?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1)
    return cleaned.strip()


def _sql_payload(question: str, project_id: int, supported: SupportedQuestion) -> PromptPayload:
    user = (
        f"{SCHEMA_DESCRIPTION}\n"
        f"project_id = {project_id}\n\n"
        f"Question type: {supported.description}\n"
        f"Question: {question.strip()}\n\n"
        "SQL:"
    )
    return PromptPayload(
        system=SQL_SYSTEM,
        user=user,
        strategy=GROUNDED,
        # The schema is the ground truth for this call: the model is expected
        # to use nothing beyond it.
        grounding_payload={
            "schema": SCHEMA_DESCRIPTION,
            "project_id": project_id,
            "question_type": supported.key,
        },
    )


def _phrase_payload(question: str, result: QueryResult) -> PromptPayload:
    rows = json.dumps(result.rows, indent=2, default=str)
    user = (
        f"Question: {question.strip()}\n\n"
        f"Query executed:\n```sql\n{result.sql}\n```\n\n"
        f"Result set ({result.row_count} rows):\n```json\n{rows}\n```\n\n"
        "Answer:"
    )
    return PromptPayload(
        system=PHRASE_SYSTEM,
        user=user,
        strategy=GROUNDED,
        grounding_payload={"sql": result.sql, "rows": result.rows},
    )


def answer_question(
    session: Session, project_id: int, question: str
) -> NlQueryOutcome:
    """Answer a question, or refuse it. Caller owns the commit."""
    supported = classify(question)
    if supported is None:
        return NlQueryOutcome(
            question=question,
            in_scope=False,
            answer=out_of_scope_message(),
            refusal_reason="Question type is outside the supported set.",
        )

    sql_result = generate(
        session,
        _sql_payload(question, project_id, supported),
        project_id=project_id,
        question=question,
    )
    if not sql_result.ok:
        return NlQueryOutcome(
            question=question,
            in_scope=True,
            matched_type=supported.key,
            answer="The query service is unavailable. The dashboard and anomaly views are unaffected.",
            refusal_reason=sql_result.error,
            query_log_id=sql_result.query_log_id,
        )

    sql = _strip_fence(sql_result.text)

    if sql.upper().startswith("UNANSWERABLE"):
        return NlQueryOutcome(
            question=question,
            in_scope=False,
            matched_type=supported.key,
            answer=out_of_scope_message(),
            refusal_reason="The question cannot be answered from the available tables.",
            query_log_id=sql_result.query_log_id,
        )

    try:
        validated = validate(sql, project_id)
    except UnsafeQuery as exc:
        return NlQueryOutcome(
            question=question,
            in_scope=True,
            matched_type=supported.key,
            answer="I could not produce a safe query for that question.",
            refusal_reason=str(exc),
            query_log_id=sql_result.query_log_id,
            metadata={"rejected_sql": sql},
        )

    try:
        result = run(validated)
    except QueryFailed as exc:
        return NlQueryOutcome(
            question=question,
            in_scope=True,
            matched_type=supported.key,
            answer="The query could not be completed.",
            refusal_reason=str(exc),
            query_log_id=sql_result.query_log_id,
        )

    phrased = generate(
        session,
        _phrase_payload(question, result),
        project_id=project_id,
        question=question,
        generated_sql=result.sql,
    )

    return NlQueryOutcome(
        question=question,
        in_scope=True,
        matched_type=supported.key,
        answer=phrased.text if phrased.ok else "The result could not be summarised.",
        refusal_reason=phrased.error,
        result=result,
        query_log_id=phrased.query_log_id,
        metadata={"truncated": result.truncated},
    )
