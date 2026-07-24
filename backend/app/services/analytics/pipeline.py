"""Project analysis: run every KPI and detector, and persist the results.

The object this produces is the single canonical description of a project's
health. The dashboard renders it and — from FR-D2 — the generative track
receives it verbatim as its grounding payload. One structure on purpose: if the
dashboard and the LLM were fed from separate code paths they would drift, and a
hallucination check against a payload the user never saw would prove nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.analytics import Anomaly, KpiSnapshot
from app.models.project import Project, Sprint
from app.services.analytics.burndown import BurndownReport, compute_burndown
from app.services.analytics.frame import load_project_frame
from app.services.analytics.kpi import (
    DefectReport,
    DurationReport,
    VelocityReport,
    WorkloadReport,
    compute_cycle_time,
    compute_defect_density,
    compute_lead_time,
    compute_velocity,
    compute_workload,
)
from app.services.anomaly import DetectedAnomaly, detect_all


@dataclass
class ProjectAnalysis:
    project_id: int
    project_name: str
    issue_count: int
    sprint_count: int
    computed_at: datetime
    velocity: VelocityReport
    cycle_time: DurationReport
    lead_time: DurationReport
    defects: DefectReport
    burndown: BurndownReport
    workload: WorkloadReport
    anomalies: list[DetectedAnomaly] = field(default_factory=list)

    def to_dict(self, include_series: bool = True) -> dict:
        """Serialise.

        `include_series` drops the per-day burndown points. The dashboard needs
        them to draw a chart; the grounded prompt does not, and several hundred
        data points would crowd out the figures the model is meant to reason
        about.
        """
        burndown = self.burndown.to_dict()
        if not include_series:
            burndown = {
                "available": self.burndown.available,
                "sprints": [
                    {k: v for k, v in s.to_dict().items() if k != "points"}
                    for s in self.burndown.sprints
                ],
            }

        return {
            "project": {
                "id": self.project_id,
                "name": self.project_name,
                "issue_count": self.issue_count,
                "sprint_count": self.sprint_count,
                "computed_at": self.computed_at.isoformat(),
            },
            "velocity": self.velocity.to_dict(),
            "cycle_time": self.cycle_time.to_dict(),
            "lead_time": self.lead_time.to_dict(),
            "defects": self.defects.to_dict(),
            "burndown": burndown,
            "workload": self.workload.to_dict(),
            "anomalies": [a.to_dict() for a in self.anomalies],
        }


def analyse(
    frame: pd.DataFrame, project_id: int = 0, project_name: str = ""
) -> ProjectAnalysis:
    """Run the whole deterministic track over a frame. No database access."""
    return ProjectAnalysis(
        project_id=project_id,
        project_name=project_name,
        issue_count=int(len(frame)),
        sprint_count=int(frame["sprint"].nunique(dropna=True)),
        computed_at=datetime.now(timezone.utc),
        velocity=compute_velocity(frame),
        cycle_time=compute_cycle_time(frame),
        lead_time=compute_lead_time(frame),
        defects=compute_defect_density(frame),
        burndown=compute_burndown(frame),
        workload=compute_workload(frame),
        anomalies=detect_all(frame),
    )


def _snapshot_rows(
    analysis: ProjectAnalysis, sprint_ids: dict[str, int]
) -> list[KpiSnapshot]:
    """Flatten the analysis into long-format metric rows.

    Long format so FR-B5/B6 become new rows rather than a migration, and so the
    evaluation can query every metric uniformly.
    """
    rows: list[KpiSnapshot] = []

    def add(metric: str, value: float | None, sprint: str | None = None, **detail):
        rows.append(
            KpiSnapshot(
                project_id=analysis.project_id,
                sprint_id=sprint_ids.get(sprint) if sprint else None,
                metric=metric,
                value=value,
                detail=detail or None,
            )
        )

    for sprint in analysis.velocity.sprints:
        add(
            "velocity",
            sprint.velocity,
            sprint.sprint,
            completed_issues=sprint.completed_issues,
            total_issues=sprint.total_issues,
            unestimated_completed=sprint.unestimated_completed,
        )

    # Availability travels with the value, as it does for the duration metrics
    # below: a NULL row means "not measurable", and the evaluation has to be
    # able to tell that apart from a metric nobody wrote.
    add(
        "velocity_mean",
        analysis.velocity.mean,
        available=analysis.velocity.available,
        unavailable_reason=analysis.velocity.unavailable_reason,
    )
    add("velocity_median", analysis.velocity.median, available=analysis.velocity.available)
    add("velocity_stdev", analysis.velocity.stdev, available=analysis.velocity.available)

    for report in (analysis.cycle_time, analysis.lead_time):
        # Availability is recorded even when the metric could not be computed:
        # "not measurable from this export" is itself a finding the dashboard
        # and the summary both need to state.
        add(
            f"{report.metric}_median",
            report.median_days,
            available=report.available,
            sample_size=report.sample_size,
            unavailable_reason=report.unavailable_reason,
        )
        add(f"{report.metric}_mean", report.mean_days, available=report.available)
        add(f"{report.metric}_p85", report.p85_days, available=report.available)
        for entry in report.by_sprint:
            add(
                f"{report.metric}_median",
                entry["median_days"],
                entry["sprint"],
                sample_size=entry["sample_size"],
            )

    add(
        "defect_ratio",
        analysis.defects.defect_ratio,
        defect_count=analysis.defects.defect_count,
        total_issues=analysis.defects.total_issues,
    )
    add("defect_density", analysis.defects.defect_density)
    for entry in analysis.defects.by_sprint:
        add(
            "defect_ratio",
            entry["defect_ratio"],
            entry["sprint"],
            defect_count=entry["defect_count"],
            total_issues=entry["total_issues"],
        )

    for sprint in analysis.burndown.sprints:
        add("scope_added", sprint.scope_added, sprint.sprint, final_scope=sprint.final_scope)

    # Per-assignee, so sprint_id stays null. Preserved as instrumentation like
    # every other metric, not only rendered (.claude/rules/data-model.md).
    for person in analysis.workload.people:
        add(
            "workload_issues",
            person.issue_count,
            assignee=person.assignee,
            story_points=person.story_points,
            done=person.done_count,
            blocked=person.blocked_count,
            open=person.open_count,
        )

    return rows


def persist_analysis(
    session: Session, analysis: ProjectAnalysis, sprint_ids: dict[str, int]
) -> tuple[int, int]:
    """Replace the project's stored KPIs and anomalies. Caller owns the commit.

    Recomputation is a full replacement rather than an append: a stale snapshot
    from a previous run would silently be treated as current by the dashboard
    and by anything scoring the LLM's claims.
    """
    session.execute(
        delete(KpiSnapshot).where(KpiSnapshot.project_id == analysis.project_id)
    )
    session.execute(delete(Anomaly).where(Anomaly.project_id == analysis.project_id))

    snapshots = _snapshot_rows(analysis, sprint_ids)
    session.add_all(snapshots)

    anomalies = [
        Anomaly(
            project_id=analysis.project_id,
            sprint_id=sprint_ids.get(a.sprint),
            anomaly_type=a.anomaly_type,
            severity=a.severity,
            detail=a.detail,
        )
        for a in analysis.anomalies
    ]
    session.add_all(anomalies)

    return len(snapshots), len(anomalies)


def run_analysis(session: Session, project_id: int) -> ProjectAnalysis:
    """Load, analyse and persist. Caller owns the commit."""
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    frame = load_project_frame(session, project_id)
    analysis = analyse(frame, project_id=project_id, project_name=project.name)

    sprint_ids = {
        s.name: s.id
        for s in session.scalars(
            select(Sprint).where(Sprint.project_id == project_id)
        ).all()
    }

    persist_analysis(session, analysis, sprint_ids)
    return analysis
