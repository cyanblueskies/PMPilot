"""Persist a parsed upload: DataFrame -> Project / Sprint / Issue rows."""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.models.project import Issue, Project, Sprint
from app.services.ingestion.loader import IngestResult


def _optional(row: pd.Series, column: str):
    """Read a column that may not exist, mapping pandas NA to None.

    Optional fields are absent entirely when the export lacked the column, so
    a plain row[column] would raise rather than yield a null.
    """
    if column not in row.index:
        return None
    value = row[column]
    return None if pd.isna(value) else value


def _sprint_order(frame: pd.DataFrame) -> list[str]:
    """Order sprints chronologically.

    Derived from the earliest issue timestamp in each sprint rather than from
    the sprint name. Names like "Sprint 10" sort before "Sprint 2"
    lexicographically, and plenty of teams don't number them at all.
    """
    names = [n for n in frame["sprint"].dropna().unique()]

    if "created_date" in frame.columns:
        first_seen = frame.groupby("sprint")["created_date"].min()
        # Sprints whose issues all lack a date fall to the end, in file order.
        return sorted(
            names,
            key=lambda n: (
                pd.isna(first_seen.get(n)),
                first_seen.get(n) if not pd.isna(first_seen.get(n)) else 0,
            ),
        )
    return names


def persist(session: Session, project: Project, result: IngestResult) -> int:
    """Write sprints and issues for an already-created project.

    Returns the number of issues written. Caller owns the transaction.
    """
    frame = result.frame

    sprint_ids: dict[str, int] = {}
    for sequence, name in enumerate(_sprint_order(frame)):
        rows = frame[frame["sprint"] == name]

        start = end = None
        if "created_date" in frame.columns and rows["created_date"].notna().any():
            start = rows["created_date"].min().to_pydatetime()
        if "resolved_date" in frame.columns and rows["resolved_date"].notna().any():
            end = rows["resolved_date"].max().to_pydatetime()

        sprint = Sprint(
            project_id=project.id,
            name=str(name),
            sequence=sequence,
            start_date=start,
            end_date=end,
        )
        session.add(sprint)
        session.flush()  # need the id before attaching issues
        sprint_ids[name] = sprint.id

    issues = []
    for _, row in frame.iterrows():
        sprint_name = _optional(row, "sprint")
        story_points = _optional(row, "story_points")
        original_estimate = _optional(row, "original_estimate")
        time_spent = _optional(row, "time_spent")

        issues.append(
            Issue(
                project_id=project.id,
                sprint_id=sprint_ids.get(sprint_name) if sprint_name else None,
                issue_key=str(row["issue_key"]),
                issue_type=_optional(row, "issue_type"),
                status=_optional(row, "status"),
                assignee=_optional(row, "assignee"),
                reporter=_optional(row, "reporter"),
                priority=_optional(row, "priority"),
                story_points=float(story_points) if story_points is not None else None,
                created_date=_optional(row, "created_date"),
                started_date=_optional(row, "started_date"),
                resolved_date=_optional(row, "resolved_date"),
                due_date=_optional(row, "due_date"),
                labels=_optional(row, "labels"),
                epic_link=_optional(row, "epic_link"),
                original_estimate=(
                    int(original_estimate) if original_estimate is not None else None
                ),
                time_spent=int(time_spent) if time_spent is not None else None,
                description=_optional(row, "description"),
                comments=_optional(row, "comments"),
            )
        )

    session.add_all(issues)
    return len(issues)
