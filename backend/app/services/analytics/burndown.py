"""FR-B2 — burndown and burnup series.

One point per day of the sprint. Scope is recomputed at each point rather than
fixed at the start, so work added mid-sprint shows up as the scope line rising
instead of silently making the team look slower.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from app.services.analytics.kpi import is_done

# Used when a sprint has no resolved work and no due dates to bound it.
DEFAULT_SPRINT_DAYS = 14
# 5,000 issues over 20 sprints is the design point; a runaway date range would
# blow the <5s budget without adding information.
MAX_POINTS_PER_SPRINT = 90


@dataclass
class BurndownPoint:
    date: str
    scope_points: float
    completed_points: float
    remaining_points: float
    ideal_remaining: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SprintBurndown:
    sprint: str
    sequence: int
    start: str
    end: str
    initial_scope: float
    final_scope: float
    completed: float
    # Points added after the sprint began. The burnup's scope line makes this
    # visible; naming it here saves every consumer from re-deriving it.
    scope_added: float
    points: list[BurndownPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sprint": self.sprint,
            "sequence": self.sequence,
            "start": self.start,
            "end": self.end,
            "initial_scope": self.initial_scope,
            "final_scope": self.final_scope,
            "completed": self.completed,
            "scope_added": self.scope_added,
            "points": [p.to_dict() for p in self.points],
        }


@dataclass
class BurndownReport:
    available: bool
    sprints: list[SprintBurndown] = field(default_factory=list)
    unavailable_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "sprints": [s.to_dict() for s in self.sprints],
            "unavailable_reason": self.unavailable_reason,
        }


def _sprint_bounds(rows: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Infer sprint start and end from issue timestamps.

    The frame carries no sprint calendar — a Jira CSV export has no sprint
    start/end columns — so the window is derived from the work itself.
    """
    # Prefer when work began over when issues were raised. Most of a sprint's
    # backlog is created days or weeks earlier, so min(created_date) would put
    # the sprint start well before the sprint actually ran and make almost all
    # scope look like it arrived on day one.
    start = rows["started_date"].min()
    if pd.isna(start):
        start = rows["created_date"].min()

    # The window must reach the last resolution, not just the nominal sprint
    # end: work often lands a day or two late, and a window that stops short
    # makes the final series point disagree with the sprint's own total.
    candidates = [rows["resolved_date"].max(), rows["due_date"].max()]
    end = max((c for c in candidates if pd.notna(c)), default=pd.NaT)

    if pd.isna(end) or end <= start:
        end = start + pd.Timedelta(days=DEFAULT_SPRINT_DAYS)

    # Normalise both before any day arithmetic. Mixing a normalised start with
    # a raw end drops a day whenever the start's time-of-day is later than the
    # end's, which silently truncates the series.
    return start.normalize(), end.normalize()


def compute_burndown(frame: pd.DataFrame) -> BurndownReport:
    """FR-B2 — daily remaining and completed work per sprint."""
    if frame.empty or frame["sprint"].isna().all():
        return BurndownReport(available=False, unavailable_reason="No sprint data.")

    if frame["created_date"].isna().all():
        return BurndownReport(
            available=False,
            unavailable_reason=(
                "No usable values in created_date. A burndown needs to know when "
                "work entered the sprint."
            ),
        )

    done = is_done(frame)
    sprints: list[SprintBurndown] = []

    ordered = (
        frame[["sprint", "sprint_sequence"]]
        .dropna(subset=["sprint"])
        .drop_duplicates(subset=["sprint"])
        .sort_values("sprint_sequence", na_position="last")
    )

    for _, meta in ordered.iterrows():
        name = meta["sprint"]
        mask = frame["sprint"] == name
        rows = frame[mask]
        rows_done = frame[mask & done]

        if rows["created_date"].isna().all() and rows["started_date"].isna().all():
            continue

        start, end = _sprint_bounds(rows)
        days = min((end - start).days + 1, MAX_POINTS_PER_SPRINT)
        dates = pd.date_range(start=start, periods=max(days, 1), freq="D")

        # Scope at the first point, used to anchor the ideal line.
        first_day_end = dates[0] + pd.Timedelta(days=1)
        initial_scope = float(
            rows.loc[rows["created_date"] < first_day_end, "story_points"].sum(skipna=True)
        )
        final_scope = float(rows["story_points"].sum(skipna=True))
        completed_total = float(rows_done["story_points"].sum(skipna=True))

        points: list[BurndownPoint] = []
        last_index = len(dates) - 1
        for i, day in enumerate(dates):
            cutoff = day + pd.Timedelta(days=1)

            scope = float(
                rows.loc[rows["created_date"] < cutoff, "story_points"].sum(skipna=True)
            )
            completed = float(
                rows_done.loc[
                    rows_done["resolved_date"] < cutoff, "story_points"
                ].sum(skipna=True)
            )

            # Straight line from the starting scope to zero at the last point.
            ideal = (
                initial_scope * (1 - i / last_index) if last_index > 0 else 0.0
            )

            points.append(
                BurndownPoint(
                    date=day.date().isoformat(),
                    scope_points=round(scope, 2),
                    completed_points=round(completed, 2),
                    remaining_points=round(scope - completed, 2),
                    ideal_remaining=round(max(ideal, 0.0), 2),
                )
            )

        sprints.append(
            SprintBurndown(
                sprint=str(name),
                sequence=int(meta["sprint_sequence"])
                if pd.notna(meta["sprint_sequence"])
                else len(sprints),
                start=start.date().isoformat(),
                end=end.date().isoformat(),
                initial_scope=round(initial_scope, 2),
                final_scope=round(final_scope, 2),
                completed=round(completed_total, 2),
                scope_added=round(final_scope - initial_scope, 2),
                points=points,
            )
        )

    return BurndownReport(available=True, sprints=sprints)
