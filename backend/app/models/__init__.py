"""ORM models.

Every model must be imported here. Alembic's autogenerate only sees tables
registered on Base.metadata, and a model that is never imported is never
registered — the migration comes out silently missing that table.
"""

from app.models.analytics import Anomaly, KpiSnapshot
from app.models.base import Base
from app.models.llm import QueryLog, Report
from app.models.project import Issue, Project, Sprint

__all__ = [
    "Base",
    "Project",
    "Sprint",
    "Issue",
    "KpiSnapshot",
    "Anomaly",
    "QueryLog",
    "Report",
]
