"""The canonical analytics DataFrame.

Both entry points — a freshly parsed upload and a project loaded from the
database — must produce the same shape, so KPI code has exactly one input
contract and can be tested without a database.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Issue, Sprint

# Sprint ordering matters for velocity trends and Z-scores, so it travels with
# the frame rather than being re-derived by every caller.
COLUMNS = (
    "issue_key",
    "issue_type",
    "status",
    "assignee",
    "reporter",
    "priority",
    "story_points",
    "sprint",
    "sprint_sequence",
    "created_date",
    "started_date",
    "resolved_date",
    "due_date",
    "labels",
    "epic_link",
    "original_estimate",
    "time_spent",
)

DATE_COLUMNS = ("created_date", "started_date", "resolved_date", "due_date")


def load_project_frame(session: Session, project_id: int) -> pd.DataFrame:
    """Read a project's issues into the canonical frame."""
    rows = session.execute(
        select(Issue, Sprint.name, Sprint.sequence)
        .outerjoin(Sprint, Issue.sprint_id == Sprint.id)
        .where(Issue.project_id == project_id)
    ).all()

    records = [
        {
            "issue_key": issue.issue_key,
            "issue_type": issue.issue_type,
            "status": issue.status,
            "assignee": issue.assignee,
            "reporter": issue.reporter,
            "priority": issue.priority,
            "story_points": issue.story_points,
            "sprint": sprint_name,
            "sprint_sequence": sequence,
            "created_date": issue.created_date,
            "started_date": issue.started_date,
            "resolved_date": issue.resolved_date,
            "due_date": issue.due_date,
            "labels": issue.labels,
            "epic_link": issue.epic_link,
            "original_estimate": issue.original_estimate,
            "time_spent": issue.time_spent,
        }
        for issue, sprint_name, sequence in rows
    ]

    return ensure_frame(pd.DataFrame.from_records(records, columns=list(COLUMNS)))


def ensure_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Add any missing canonical columns and fix dtypes.

    An upload whose export lacked a column arrives without it entirely; adding
    it as all-NA here means KPI code can assume the column exists and only has
    to handle missing *values*, not missing columns.
    """
    frame = frame.copy()

    for column in COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    for column in DATE_COLUMNS:
        # utc=True on an all-NA column still yields a tz-aware dtype, so
        # subtraction downstream never mixes naive and aware timestamps.
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")

    frame["story_points"] = pd.to_numeric(frame["story_points"], errors="coerce")

    if frame["sprint_sequence"].isna().all():
        # Frames built straight from an upload have no sprint table yet. Order
        # by first appearance so velocity trends are still meaningful.
        order = {name: i for i, name in enumerate(frame["sprint"].dropna().unique())}
        frame["sprint_sequence"] = frame["sprint"].map(order)

    frame["sprint_sequence"] = pd.to_numeric(frame["sprint_sequence"], errors="coerce")

    return frame[list(COLUMNS)]
