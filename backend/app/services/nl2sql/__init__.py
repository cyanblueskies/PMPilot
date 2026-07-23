"""FR-D1 — NL2SQL over structured fields, bounded to a predefined question set."""

from app.services.nl2sql.engine import NlQueryOutcome, answer_question
from app.services.nl2sql.execute import QueryFailed, QueryResult, run
from app.services.nl2sql.questions import (
    SUPPORTED_QUESTIONS,
    SupportedQuestion,
    classify,
    out_of_scope_message,
)
from app.services.nl2sql.safety import (
    ALLOWED_TABLES,
    MAX_ROWS,
    UnsafeQuery,
    ValidatedQuery,
    validate,
)

__all__ = [
    "answer_question",
    "NlQueryOutcome",
    "classify",
    "SUPPORTED_QUESTIONS",
    "SupportedQuestion",
    "out_of_scope_message",
    "validate",
    "ValidatedQuery",
    "UnsafeQuery",
    "ALLOWED_TABLES",
    "MAX_ROWS",
    "run",
    "QueryResult",
    "QueryFailed",
]
