"""FR-B — KPI computation.

Pure functions: data in, values out. No database access, no framework, no LLM
imports — this module must be testable in isolation (.claude/rules/architecture.md).

Every return value is JSON-serialisable, because this output is exactly what
the generative track receives and what its claims are later scored against.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

# Status vocabularies vary between Jira configurations, so matching is on the
# normalised text rather than an exact enum. Anything unrecognised is treated
# as not-done, which understates rather than overstates progress.
DONE_STATUSES = frozenset({"done", "closed", "resolved", "complete", "completed"})
BLOCKED_STATUSES = frozenset({"blocked", "impeded", "on hold"})
DEFECT_TYPES = frozenset({"bug", "defect", "fault"})


def _norm(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower()


def is_done(frame: pd.DataFrame) -> pd.Series:
    return _norm(frame["status"]).isin(DONE_STATUSES).fillna(False)


def is_blocked(frame: pd.DataFrame) -> pd.Series:
    return _norm(frame["status"]).isin(BLOCKED_STATUSES).fillna(False)


def is_defect(frame: pd.DataFrame) -> pd.Series:
    return _norm(frame["issue_type"]).isin(DEFECT_TYPES).fillna(False)


@dataclass
class SprintVelocity:
    sprint: str
    sequence: int
    velocity: float
    completed_issues: int
    total_issues: int
    # Done issues carrying no estimate. Reported rather than folded in: counting
    # them as zero understates velocity, and silently dropping them hides that
    # the figure is based on partial data.
    unestimated_completed: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VelocityReport:
    sprints: list[SprintVelocity] = field(default_factory=list)
    mean: float | None = None
    median: float | None = None
    stdev: float | None = None
    # True when any sprint completed work that carried no estimate, so a
    # consumer can qualify the number instead of quoting it flat.
    has_unestimated_work: bool = False

    def to_dict(self) -> dict:
        return {
            "sprints": [s.to_dict() for s in self.sprints],
            "mean": self.mean,
            "median": self.median,
            "stdev": self.stdev,
            "has_unestimated_work": self.has_unestimated_work,
        }


def compute_velocity(frame: pd.DataFrame) -> VelocityReport:
    """FR-B1 — story points completed per sprint.

    Only issues in a done status count. Unfinished work contributes nothing,
    which is the standard definition: velocity measures delivered capacity, not
    attempted capacity.
    """
    if frame.empty or frame["sprint"].isna().all():
        return VelocityReport()

    working = frame.copy()
    working["_done"] = is_done(working)

    sprints: list[SprintVelocity] = []
    ordered = (
        working[["sprint", "sprint_sequence"]]
        .dropna(subset=["sprint"])
        .drop_duplicates(subset=["sprint"])
        .sort_values("sprint_sequence", na_position="last")
    )

    for _, meta in ordered.iterrows():
        name = meta["sprint"]
        rows = working[working["sprint"] == name]
        done = rows[rows["_done"]]

        sprints.append(
            SprintVelocity(
                sprint=str(name),
                sequence=int(meta["sprint_sequence"])
                if pd.notna(meta["sprint_sequence"])
                else len(sprints),
                velocity=float(done["story_points"].sum(skipna=True)),
                completed_issues=int(len(done)),
                total_issues=int(len(rows)),
                unestimated_completed=int(done["story_points"].isna().sum()),
            )
        )

    values = pd.Series([s.velocity for s in sprints], dtype="float64")

    return VelocityReport(
        sprints=sprints,
        mean=round(float(values.mean()), 2) if len(values) else None,
        median=round(float(values.median()), 2) if len(values) else None,
        # Sample stdev (ddof=1) — these sprints are a sample of the team's
        # behaviour, not the entire population of sprints they will ever run.
        # Undefined for a single sprint, which is correct: one observation
        # carries no information about spread.
        stdev=round(float(values.std(ddof=1)), 2) if len(values) > 1 else None,
        has_unestimated_work=any(s.unestimated_completed for s in sprints),
    )


@dataclass
class DurationReport:
    """A duration metric in days, summarised.

    `available` is False when the source columns are missing entirely, which is
    different from a metric that computed to nothing. A consumer must be able to
    say "not measurable from this export" rather than reporting an absence as a
    result.
    """

    metric: str
    available: bool
    definition: str
    sample_size: int = 0
    mean_days: float | None = None
    median_days: float | None = None
    p85_days: float | None = None
    by_sprint: list[dict] = field(default_factory=list)
    unavailable_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _summarise_days(deltas: pd.Series) -> dict:
    days = deltas.dt.total_seconds() / 86400
    days = days[days.notna()]
    # A negative duration means the timestamps contradict each other (resolved
    # before started). Excluded rather than averaged in, where it would silently
    # pull the mean down.
    days = days[days >= 0]
    if days.empty:
        return {"sample_size": 0, "mean_days": None, "median_days": None, "p85_days": None}
    return {
        "sample_size": int(len(days)),
        "mean_days": round(float(days.mean()), 2),
        "median_days": round(float(days.median()), 2),
        # 85th percentile is the figure teams forecast with — it answers "most
        # work finishes within N days" far better than the mean, which a few
        # long-running items distort.
        "p85_days": round(float(days.quantile(0.85)), 2),
    }


def _duration_report(
    frame: pd.DataFrame, metric: str, start: str, end: str, definition: str
) -> DurationReport:
    # Availability is decided by the *start* column alone, because that is what
    # defines the metric. An empty end column means nothing has been completed
    # yet — a sample size of zero, not an unmeasurable metric. Reporting "cannot
    # be measured" when the real answer is "nothing has finished" would be a
    # different and misleading claim.
    if frame.empty or frame[start].isna().all():
        return DurationReport(
            metric=metric,
            available=False,
            definition=definition,
            unavailable_reason=(
                f"No usable values in {start}. "
                "This export does not carry the timestamp the metric needs."
            ),
        )

    done = frame[is_done(frame)]
    deltas = done[end] - done[start]
    summary = _summarise_days(deltas)

    by_sprint = []
    ordered = (
        done[["sprint", "sprint_sequence"]]
        .dropna(subset=["sprint"])
        .drop_duplicates(subset=["sprint"])
        .sort_values("sprint_sequence", na_position="last")
    )
    for _, meta in ordered.iterrows():
        name = meta["sprint"]
        rows = done[done["sprint"] == name]
        by_sprint.append(
            {"sprint": str(name), **_summarise_days(rows[end] - rows[start])}
        )

    return DurationReport(
        metric=metric,
        available=True,
        definition=definition,
        by_sprint=by_sprint,
        **summary,
    )


def compute_cycle_time(frame: pd.DataFrame) -> DurationReport:
    """FR-B3 — time from work starting to completion.

    Needs `started_date`, which standard Jira CSV exports usually omit. When it
    is absent the report is marked unavailable rather than silently falling back
    to lead time — quietly reporting one metric under the other's name would
    make the number wrong in a way nobody could see.
    """
    return _duration_report(
        frame,
        metric="cycle_time",
        start="started_date",
        end="resolved_date",
        definition="days from work starting (started_date) to resolution",
    )


def compute_lead_time(frame: pd.DataFrame) -> DurationReport:
    """FR-B3 — time from an issue being raised to completion."""
    return _duration_report(
        frame,
        metric="lead_time",
        start="created_date",
        end="resolved_date",
        definition="days from creation to resolution",
    )


@dataclass
class DefectReport:
    total_issues: int
    defect_count: int
    defect_ratio: float | None
    # Defects per completed story point. None when nothing estimated has been
    # completed — dividing by zero delivered points is undefined, not zero.
    defect_density: float | None
    by_sprint: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_defect_density(frame: pd.DataFrame) -> DefectReport:
    """FR-B4 — bug share of the backlog, and defects per delivered point."""
    if frame.empty:
        return DefectReport(total_issues=0, defect_count=0, defect_ratio=None, defect_density=None)

    defects = is_defect(frame)
    done = is_done(frame)

    delivered_points = float(frame.loc[done, "story_points"].sum(skipna=True))
    total = int(len(frame))
    count = int(defects.sum())

    by_sprint = []
    ordered = (
        frame[["sprint", "sprint_sequence"]]
        .dropna(subset=["sprint"])
        .drop_duplicates(subset=["sprint"])
        .sort_values("sprint_sequence", na_position="last")
    )
    for _, meta in ordered.iterrows():
        name = meta["sprint"]
        mask = frame["sprint"] == name
        rows_total = int(mask.sum())
        rows_defects = int((mask & defects).sum())
        by_sprint.append(
            {
                "sprint": str(name),
                "total_issues": rows_total,
                "defect_count": rows_defects,
                "defect_ratio": round(rows_defects / rows_total, 4) if rows_total else None,
            }
        )

    return DefectReport(
        total_issues=total,
        defect_count=count,
        defect_ratio=round(count / total, 4) if total else None,
        defect_density=(
            round(count / delivered_points, 4) if delivered_points > 0 else None
        ),
        by_sprint=by_sprint,
    )
