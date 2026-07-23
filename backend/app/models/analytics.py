"""Deterministic track output: computed KPIs and detected anomalies.

These are the *only* things the generative track is allowed to see
(.claude/rules/architecture.md). They are also evaluation instrumentation, not
caches — preserve their write paths.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now_column


class KpiSnapshot(Base):
    """One metric value for one sprint, in long format.

    Long rather than a column per KPI: adding FR-B5/B6 later becomes a new row
    rather than a migration, and the evaluation can query metrics uniformly.
    """

    __tablename__ = "kpi_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    sprint_id: Mapped[int | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="CASCADE"), index=True
    )

    # e.g. "velocity", "cycle_time_median", "defect_density"
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float | None]
    # Units, sample size, and anything else needed to interpret `value` later.
    detail: Mapped[dict | None] = mapped_column(JSONB)

    computed_at: Mapped[datetime] = utc_now_column()

    __table_args__ = (
        Index("ix_kpi_project_metric", "project_id", "metric"),
        Index("ix_kpi_sprint_metric", "sprint_id", "metric"),
    )


class Anomaly(Base):
    """One detected anomaly.

    `anomaly_type` uses the same vocabulary as the FR-A4 ground-truth manifest
    (velocity_drop / overdue_pileup / blocked_cluster) so detection F1 is a
    direct comparison rather than a mapping exercise.
    """

    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    sprint_id: Mapped[int | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="CASCADE"), index=True
    )

    anomaly_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[float | None]
    # The evidence: z-score, threshold, counts, affected issue keys. This is what
    # the grounded prompt cites, so it must be self-contained.
    detail: Mapped[dict | None] = mapped_column(JSONB)

    detected_at: Mapped[datetime] = utc_now_column()

    __table_args__ = (Index("ix_anomalies_project_type", "project_id", "anomaly_type"),)
