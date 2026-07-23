"""Source data: what was uploaded, as ingested.

These tables hold the raw material. Everything the deterministic track derives
from them lives in analytics.py.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utc_now_column


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = utc_now_column()

    sprints: Mapped[list["Sprint"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Nullable: a Jira export may not carry sprint dates, and the KPI engine
    # falls back to deriving them from issue timestamps.
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = utc_now_column()

    project: Mapped["Project"] = relationship(back_populates="sprints")
    issues: Mapped[list["Issue"]] = relationship(back_populates="sprint")

    __table_args__ = (Index("ix_sprints_project_sequence", "project_id", "sequence"),)


class Issue(Base):
    """The fact table. One row per Jira issue.

    Column names are the internal schema, not the CSV headers — field mapping
    (FR-A2) translates at the ingestion boundary so analytics never depends on
    a particular export's header text.
    """

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    sprint_id: Mapped[int | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), index=True
    )

    issue_key: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(50))
    assignee: Mapped[str | None] = mapped_column(String(200))
    reporter: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[str | None] = mapped_column(String(50))

    # Nullable and NOT defaulted to 0: an unestimated issue is not a zero-point
    # issue, and conflating them distorts velocity.
    story_points: Mapped[float | None]

    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    labels: Mapped[str | None] = mapped_column(String(500))
    epic_link: Mapped[str | None] = mapped_column(String(100))
    original_estimate: Mapped[int | None]
    time_spent: Mapped[int | None]
    description: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="issues")
    sprint: Mapped["Sprint | None"] = relationship(back_populates="issues")

    __table_args__ = (
        Index("ix_issues_project_key", "project_id", "issue_key"),
        Index("ix_issues_project_status", "project_id", "status"),
    )
