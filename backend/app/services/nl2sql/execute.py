"""Read-only execution for FR-D1.

Defence layers 2 and 3 from .claude/rules/security.md: a role with SELECT-only
grants, plus a statement timeout and a bounded result set.

The read-only role is the layer that holds if the statement whitelist is ever
bypassed, which is exactly why it exists even though the whitelist is already
there. Never route these queries through the application's own connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

from app.db.session import readonly_engine
from app.services.nl2sql.safety import ValidatedQuery

STATEMENT_TIMEOUT_MS = 5000


class QueryFailed(RuntimeError):
    """Execution failed. The message is safe to show a user."""


@dataclass
class QueryResult:
    sql: str
    rows: list[dict]
    row_count: int
    truncated: bool


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def run(query: ValidatedQuery) -> QueryResult:
    """Execute a validated statement on the read-only connection."""
    try:
        with readonly_engine.connect() as conn:
            # Per-transaction, so a runaway query is cut off by the database
            # rather than relying on the application to notice.
            conn.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
            result = conn.execute(text(query.sql))
            columns = list(result.keys())
            fetched = result.fetchmany(query.row_limit + 1)
    except Exception as exc:  # noqa: BLE001
        raise QueryFailed(
            f"The query could not be executed: {type(exc).__name__}."
        ) from exc

    truncated = len(fetched) > query.row_limit
    rows = [
        {column: _jsonable(value) for column, value in zip(columns, row)}
        for row in fetched[: query.row_limit]
    ]

    return QueryResult(
        sql=query.sql, rows=rows, row_count=len(rows), truncated=truncated
    )
