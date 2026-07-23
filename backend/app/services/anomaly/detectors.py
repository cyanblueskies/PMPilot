"""FR-C1 / FR-C2 / FR-C3 — statistical anomaly detectors.

Each detector compares a sprint against the project's own history rather than
an absolute benchmark: a team completing 30 points a sprint is not unhealthy,
but a team that normally completes 120 and suddenly completes 30 is.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.analytics.kpi import is_blocked, is_done
from app.services.anomaly.base import (
    BLOCKED_CLUSTER,
    MIN_SPRINTS_FOR_COMPARISON,
    OVERDUE_PILEUP,
    VELOCITY_DROP,
    DetectedAnomaly,
    clamp_severity,
)


def _sprint_index(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame[["sprint", "sprint_sequence"]]
        .dropna(subset=["sprint"])
        .drop_duplicates(subset=["sprint"])
        .sort_values("sprint_sequence", na_position="last")
    )


def _iqr_bounds(values: pd.Series, multiplier: float = 1.5) -> tuple[float, float]:
    q1, q3 = float(values.quantile(0.25)), float(values.quantile(0.75))
    iqr = q3 - q1
    return q1 - multiplier * iqr, q3 + multiplier * iqr


# Scales the median absolute deviation so that, for normally distributed data,
# the modified Z-score is comparable to an ordinary one.
MAD_SCALE = 0.6745


def _modified_z(values: pd.Series) -> pd.Series:
    """Z-score built on median and MAD rather than mean and standard deviation.

    An ordinary Z-score is distorted by the very outlier it is meant to find:
    one unusually high sprint inflates the standard deviation and hides a real
    drop. On a six-sprint project this was enough to miss a sprint delivering
    half the median. Median and MAD are unaffected by that.
    """
    median = float(values.median())
    mad = float((values - median).abs().median())
    if mad == 0:
        return pd.Series([0.0] * len(values), index=values.index, dtype="float64")
    return MAD_SCALE * (values - median) / mad


@dataclass
class VelocityDropDetector:
    """FR-C1 — sprints that delivered far less than the team's norm.

    Runs three tests and flags if any fires, because each fails differently:

    - **Z-score** is the familiar one, but the outlier it is looking for
      inflates the standard deviation and can hide itself.
    - **IQR** is robust to that, but blunt on the small samples this project
      targets (5-20 sprints).
    - **Modified Z-score** (median/MAD) is robust *and* sensitive at small
      sample sizes; it is what catches a drop masked by an unusually strong
      sprint elsewhere in the project.

    Requiring agreement instead of any-of would trade away the recall FR-C1 is
    measured on. `triggered_by` records which fired, so a finding can always be
    traced to its method.
    """

    anomaly_type: str = VELOCITY_DROP
    z_threshold: float = -1.5
    # The conventional Iglewicz-Hoaglin outlier threshold. A sweep over 50
    # generated projects (two sizes x 25 seeds) put overall F1 at 0.932 here,
    # on the plateau where tightening further changes nothing; loosening it to
    # -1.5 cost 14 percentage points of precision for no extra recall.
    modified_z_threshold: float = -3.5
    # Tukey's conventional fence. Exposed so a single method can be isolated
    # when testing which one produced a finding.
    iqr_multiplier: float = 1.5
    min_sprints: int = MIN_SPRINTS_FOR_COMPARISON

    def detect(self, frame: pd.DataFrame) -> list[DetectedAnomaly]:
        if frame.empty or frame["sprint"].isna().all():
            return []

        done = is_done(frame)
        index = _sprint_index(frame)

        velocities = []
        for _, meta in index.iterrows():
            rows = frame[(frame["sprint"] == meta["sprint"]) & done]
            velocities.append(float(rows["story_points"].sum(skipna=True)))

        if len(velocities) < self.min_sprints:
            return []

        series = pd.Series(velocities, dtype="float64")
        mean = float(series.mean())
        # Population std here, not sample: this is the set of sprints actually
        # observed, and the comparison is against that set rather than an
        # inference about sprints the team has not yet run.
        std = float(series.std(ddof=0))
        lower_bound, _ = _iqr_bounds(series, self.iqr_multiplier)
        modified = _modified_z(series)

        found: list[DetectedAnomaly] = []
        for position, (_, meta) in enumerate(index.iterrows()):
            velocity = velocities[position]

            z = (velocity - mean) / std if std > 0 else 0.0
            mz = float(modified.iloc[position])

            by_z = std > 0 and z <= self.z_threshold
            by_iqr = velocity < lower_bound
            by_modified_z = mz <= self.modified_z_threshold

            if not (by_z or by_iqr or by_modified_z):
                continue

            found.append(
                DetectedAnomaly(
                    sprint=str(meta["sprint"]),
                    sprint_sequence=int(meta["sprint_sequence"])
                    if pd.notna(meta["sprint_sequence"])
                    else position,
                    anomaly_type=self.anomaly_type,
                    severity=clamp_severity(max(abs(z), abs(mz)) / 3.0),
                    detail={
                        "velocity": round(velocity, 2),
                        "project_mean_velocity": round(mean, 2),
                        "project_median_velocity": round(float(series.median()), 2),
                        "project_stdev_velocity": round(std, 2),
                        "z_score": round(z, 2),
                        "z_threshold": self.z_threshold,
                        "modified_z_score": round(mz, 2),
                        "modified_z_threshold": self.modified_z_threshold,
                        "iqr_lower_bound": round(lower_bound, 2),
                        "triggered_by": [
                            m
                            for m, hit in (
                                ("z_score", by_z),
                                ("iqr", by_iqr),
                                ("modified_z_score", by_modified_z),
                            )
                            if hit
                        ],
                        "shortfall_vs_mean": round(mean - velocity, 2),
                    },
                )
            )

        return found


@dataclass
class OverduePileupDetector:
    """FR-C2 — unclosed work accumulating well past its due date.

    The primary signal is *how far* past due open work is, not how much of it
    there is. Counting alone cannot separate this from a velocity collapse: a
    sprint that delivered almost nothing has the highest share of open, overdue
    issues by construction, so a count- or ratio-based detector flags the
    velocity-drop sprint and misses the real pileup. Measured on the sample
    dataset, the velocity-drop sprint had the *largest* overdue share (0.79)
    but the *smallest* median lateness (3.7 days), while the genuine pileup ran
    at 13.1 days.

    The distinction is also the meaningful one: work a day late is slippage;
    work two weeks late while the sprint has moved on is a pileup.

    The ratio is kept as a materiality floor so a single very stale ticket in an
    otherwise healthy sprint does not trigger a finding.
    """

    anomaly_type: str = OVERDUE_PILEUP
    min_ratio: float = 0.20
    min_overdue: int = 3
    z_threshold: float = 1.5
    min_sprints: int = MIN_SPRINTS_FOR_COMPARISON

    def detect(self, frame: pd.DataFrame) -> list[DetectedAnomaly]:
        if frame.empty or frame["sprint"].isna().all():
            return []
        if frame["due_date"].isna().all():
            return []

        done = is_done(frame)
        index = _sprint_index(frame)

        lateness: list[float] = []
        details: list[dict] = []

        for _, meta in index.iterrows():
            mask = frame["sprint"] == meta["sprint"]
            rows = frame[mask]
            # Judged at the point the sprint's work stopped, not "now" — an old
            # project would otherwise show every open issue as overdue.
            reference = rows["resolved_date"].max()
            if pd.isna(reference):
                reference = rows["due_date"].max()

            open_rows = frame[mask & ~done]
            overdue = open_rows[open_rows["due_date"] <= reference]

            days = (reference - overdue["due_date"]).dt.total_seconds() / 86400
            total = int(len(rows))

            lateness.append(float(days.median()) if len(days) else 0.0)
            details.append(
                {
                    "overdue_issues": int(len(overdue)),
                    "total_issues": total,
                    "overdue_ratio": round(len(overdue) / total, 3) if total else 0.0,
                    "median_days_overdue": round(float(days.median()), 1)
                    if len(days)
                    else 0.0,
                    "max_days_overdue": round(float(days.max()), 1) if len(days) else 0.0,
                    # Capped: the grounded prompt needs enough to be specific,
                    # not the entire backlog.
                    "example_issue_keys": overdue["issue_key"].tolist()[:10],
                }
            )

        if len(lateness) < self.min_sprints:
            return []

        series = pd.Series(lateness, dtype="float64")
        mean = float(series.mean())
        std = float(series.std(ddof=0))

        found: list[DetectedAnomaly] = []
        for position, (_, meta) in enumerate(index.iterrows()):
            info = details[position]

            z = (lateness[position] - mean) / std if std > 0 else 0.0
            if (
                info["overdue_issues"] < self.min_overdue
                or info["overdue_ratio"] < self.min_ratio
                or z < self.z_threshold
            ):
                continue

            found.append(
                DetectedAnomaly(
                    sprint=str(meta["sprint"]),
                    sprint_sequence=int(meta["sprint_sequence"])
                    if pd.notna(meta["sprint_sequence"])
                    else position,
                    anomaly_type=self.anomaly_type,
                    severity=clamp_severity(z / 3.0),
                    detail={
                        **info,
                        "project_mean_days_overdue": round(mean, 1),
                        "z_score": round(z, 2),
                        "z_threshold": self.z_threshold,
                        "min_ratio": self.min_ratio,
                    },
                )
            )

        return found


@dataclass
class BlockedClusterDetector:
    """FR-C3 — blocked work piling up, especially on one person.

    Concentration matters as much as volume: eight blocked issues spread across
    a team is friction, whereas eight blocked on one person is usually a single
    dependency that one conversation could clear.
    """

    anomaly_type: str = BLOCKED_CLUSTER
    min_ratio: float = 0.15
    z_threshold: float = 1.5
    min_blocked: int = 3
    min_sprints: int = MIN_SPRINTS_FOR_COMPARISON

    def detect(self, frame: pd.DataFrame) -> list[DetectedAnomaly]:
        if frame.empty or frame["sprint"].isna().all():
            return []

        blocked = is_blocked(frame)
        if not blocked.any():
            return []

        index = _sprint_index(frame)
        ratios: list[float] = []
        details: list[dict] = []

        for _, meta in index.iterrows():
            mask = frame["sprint"] == meta["sprint"]
            rows = frame[mask]
            blocked_rows = frame[mask & blocked]

            total = int(len(rows))
            ratios.append(len(blocked_rows) / total if total else 0.0)

            by_assignee = (
                blocked_rows["assignee"].value_counts(dropna=True).to_dict()
                if not blocked_rows.empty
                else {}
            )
            top_assignee, top_count = (
                max(by_assignee.items(), key=lambda kv: kv[1])
                if by_assignee
                else (None, 0)
            )
            details.append(
                {
                    "blocked_issues": int(len(blocked_rows)),
                    "total_issues": total,
                    "top_assignee": top_assignee,
                    "top_assignee_blocked": int(top_count),
                    "concentration": (
                        round(top_count / len(blocked_rows), 3)
                        if len(blocked_rows)
                        else 0.0
                    ),
                    "example_issue_keys": blocked_rows["issue_key"].tolist()[:10],
                }
            )

        if len(ratios) < self.min_sprints:
            return []

        series = pd.Series(ratios, dtype="float64")
        mean = float(series.mean())
        std = float(series.std(ddof=0))

        found: list[DetectedAnomaly] = []
        for position, (_, meta) in enumerate(index.iterrows()):
            ratio = ratios[position]
            info = details[position]

            z = (ratio - mean) / std if std > 0 else 0.0
            if (
                info["blocked_issues"] < self.min_blocked
                or ratio < self.min_ratio
                or z < self.z_threshold
            ):
                continue

            found.append(
                DetectedAnomaly(
                    sprint=str(meta["sprint"]),
                    sprint_sequence=int(meta["sprint_sequence"])
                    if pd.notna(meta["sprint_sequence"])
                    else position,
                    anomaly_type=self.anomaly_type,
                    severity=clamp_severity(z / 3.0),
                    detail={
                        **info,
                        "blocked_ratio": round(ratio, 3),
                        "project_mean_ratio": round(mean, 3),
                        "z_score": round(z, 2),
                        "z_threshold": self.z_threshold,
                    },
                )
            )

        return found
