"""Declarative base and shared column conventions.

SQLAlchemy 2.0 style throughout: Mapped[] / mapped_column / select().
No legacy Query API — see .claude/rules/code-style.md.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now_column() -> Mapped[datetime]:
    """Timezone-aware creation timestamp, defaulted by the database.

    TIMESTAMPTZ everywhere: Jira exports carry offsets, and cycle/lead time are
    computed by subtracting timestamps. Naive datetimes silently shift every
    duration KPI — see .claude/rules/code-style.md.
    """
    return mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
