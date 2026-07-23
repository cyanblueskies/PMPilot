"""FR-C1 / FR-C2 / FR-C3 — anomaly detection.

Includes the boundary cases where a threshold flips, which is where a detector
silently stops working (.claude/rules/testing.md).
"""

import pandas as pd
import pytest

from app.services.analytics import ensure_frame
from app.services.anomaly import (
    BLOCKED_CLUSTER,
    OVERDUE_PILEUP,
    VELOCITY_DROP,
    BlockedClusterDetector,
    OverduePileupDetector,
    VelocityDropDetector,
    detect_all,
    score_detections,
)

DAY = pd.Timedelta(days=1)
BASE = pd.Timestamp("2026-01-05T00:00:00Z")


def sprint_rows(sprint, seq, *, points_each, count, status="Done", **extra):
    return [
        {
            "issue_key": f"{sprint}-{i}",
            "status": status,
            "story_points": points_each,
            "sprint": sprint,
            "sprint_sequence": seq,
            "created_date": BASE + seq * 14 * DAY,
            "started_date": BASE + seq * 14 * DAY,
            "resolved_date": (BASE + seq * 14 * DAY + 5 * DAY)
            if status == "Done"
            else None,
            "due_date": BASE + seq * 14 * DAY + 7 * DAY,
            **extra,
        }
        for i in range(count)
    ]


def frame_of(*groups) -> pd.DataFrame:
    rows = [r for g in groups for r in g]
    return ensure_frame(pd.DataFrame(rows))


# --- FR-C1 velocity drop ---------------------------------------------------


# Slight sprint-to-sprint variation on purpose. A perfectly constant velocity
# gives IQR = 0, and a zero-width fence makes any deviation an outlier no matter
# what multiplier is applied — which is arguably correct, but means such data
# cannot isolate one detection method from another.
STEADY_POINTS = (10, 11, 9, 12, 8, 10, 11, 9)


def steady_project(n_sprints=6, points=None, count=5):
    return [
        sprint_rows(
            f"S{i}",
            i,
            points_each=points if points is not None else STEADY_POINTS[i % len(STEADY_POINTS)],
            count=count,
        )
        for i in range(n_sprints)
    ]


def test_velocity_drop_is_detected_against_the_teams_own_norm():
    # Five sprints at 50 points, one at 5.
    groups = steady_project(5)
    groups.append(sprint_rows("S5", 5, points_each=1, count=5))

    found = VelocityDropDetector().detect(frame_of(*groups))

    assert [a.sprint for a in found] == ["S5"]
    assert found[0].anomaly_type == VELOCITY_DROP


def test_a_consistently_low_velocity_is_not_an_anomaly():
    """A slow team is not an anomalous team; only a change is."""
    found = VelocityDropDetector().detect(frame_of(*steady_project(6, points=1)))

    assert found == []


def test_detection_needs_enough_sprints_to_compare_against():
    groups = steady_project(2)
    groups.append(sprint_rows("S2", 2, points_each=1, count=5))

    assert VelocityDropDetector().detect(frame_of(*groups)) == []


def test_z_threshold_boundary_flips_the_finding():
    """Only the Z-score path is exercised, so the threshold is the sole cause.

    The detector fires if *any* of its three tests trips, so tightening one
    while the others stay lenient proves nothing about that one.
    """
    groups = steady_project(5)
    groups.append(sprint_rows("S5", 5, points_each=4, count=5))
    frame = frame_of(*groups)
    off = {"modified_z_threshold": -99.0, "iqr_multiplier": 99.0}

    lenient = VelocityDropDetector(z_threshold=-0.5, **off).detect(frame)
    strict = VelocityDropDetector(z_threshold=-4.0, **off).detect(frame)

    assert [a.sprint for a in lenient] == ["S5"]
    assert "z_score" in lenient[0].detail["triggered_by"]
    assert strict == []


def test_modified_z_catches_a_drop_that_an_ordinary_z_score_misses():
    """One unusually strong sprint inflates the standard deviation enough to
    hide a genuine drop. Median and MAD are unaffected by it.
    """
    groups = [
        sprint_rows(f"S{i}", i, points_each=p, count=5)
        for i, p in enumerate((10, 11, 9, 12))
    ]
    groups.append(sprint_rows("S4", 4, points_each=40, count=5))  # the inflater
    groups.append(sprint_rows("S5", 5, points_each=2, count=5))  # the real drop
    frame = frame_of(*groups)

    ordinary_only = VelocityDropDetector(
        modified_z_threshold=-99.0, iqr_multiplier=99.0
    ).detect(frame)
    with_modified = VelocityDropDetector(iqr_multiplier=99.0).detect(frame)

    assert ordinary_only == []
    assert [a.sprint for a in with_modified] == ["S5"]
    assert "modified_z_score" in with_modified[0].detail["triggered_by"]


def test_finding_carries_the_evidence_that_triggered_it():
    groups = steady_project(5)
    groups.append(sprint_rows("S5", 5, points_each=1, count=5))

    detail = VelocityDropDetector().detect(frame_of(*groups))[0].detail

    assert detail["velocity"] == 5
    assert detail["project_mean_velocity"] > 5
    assert detail["shortfall_vs_mean"] > 0
    assert detail["triggered_by"]  # names the method(s) that fired


# --- FR-C2 overdue pileup --------------------------------------------------


def overdue_rows(sprint, seq, count, days_late, total_extra=0):
    """`count` open issues that are `days_late` past due at the reference point."""
    reference = BASE + seq * 14 * DAY + 20 * DAY
    rows = [
        {
            "issue_key": f"{sprint}-open-{i}",
            "status": "In Progress",
            "story_points": 3,
            "sprint": sprint,
            "sprint_sequence": seq,
            "created_date": BASE + seq * 14 * DAY,
            "started_date": BASE + seq * 14 * DAY,
            "resolved_date": None,
            "due_date": reference - days_late * DAY,
        }
        for i in range(count)
    ]
    # Anchors the reference point and pads the sprint so ratios are realistic.
    rows += [
        {
            "issue_key": f"{sprint}-done-{i}",
            "status": "Done",
            "story_points": 3,
            "sprint": sprint,
            "sprint_sequence": seq,
            "created_date": BASE + seq * 14 * DAY,
            "started_date": BASE + seq * 14 * DAY,
            "resolved_date": reference,
            "due_date": reference - DAY,
        }
        for i in range(total_extra)
    ]
    return rows


def test_overdue_pileup_is_detected_when_work_is_far_past_due():
    groups = [overdue_rows(f"S{i}", i, count=2, days_late=2, total_extra=8) for i in range(5)]
    groups.append(overdue_rows("S5", 5, count=6, days_late=20, total_extra=6))

    found = OverduePileupDetector().detect(frame_of(*groups))

    assert [a.sprint for a in found] == ["S5"]
    assert found[0].detail["median_days_overdue"] == 20


def test_mild_lateness_across_many_issues_is_not_a_pileup():
    """Volume alone is not the signal — otherwise a stalled sprint always fires."""
    groups = [overdue_rows(f"S{i}", i, count=2, days_late=5, total_extra=8) for i in range(5)]
    groups.append(overdue_rows("S5", 5, count=9, days_late=5, total_extra=1))

    assert OverduePileupDetector().detect(frame_of(*groups)) == []


def test_a_single_very_stale_issue_does_not_trigger():
    groups = [overdue_rows(f"S{i}", i, count=2, days_late=2, total_extra=8) for i in range(5)]
    groups.append(overdue_rows("S5", 5, count=1, days_late=40, total_extra=9))

    assert OverduePileupDetector().detect(frame_of(*groups)) == []


def test_overdue_detection_is_skipped_without_due_dates():
    groups = steady_project(6)
    frame = frame_of(*groups)
    frame["due_date"] = pd.NaT

    assert OverduePileupDetector().detect(frame) == []


# --- FR-C3 blocked clustering ----------------------------------------------


def test_blocked_cluster_is_detected():
    groups = [sprint_rows(f"S{i}", i, points_each=3, count=10) for i in range(5)]
    groups.append(
        sprint_rows("S5", 5, points_each=3, count=6, status="Blocked", assignee="alice")
        + sprint_rows("S5b", 5, points_each=3, count=4)
    )
    frame = frame_of(*groups)
    frame.loc[frame["sprint"] == "S5b", "sprint"] = "S5"

    found = BlockedClusterDetector().detect(frame)

    assert [a.sprint for a in found] == ["S5"]
    assert found[0].detail["blocked_issues"] == 6


def test_blocked_finding_names_the_person_it_concentrates_on():
    groups = [sprint_rows(f"S{i}", i, points_each=3, count=10) for i in range(5)]
    blocked = sprint_rows(
        "S5", 5, points_each=3, count=5, status="Blocked", assignee="alice"
    )
    blocked[0]["assignee"] = "bob"
    groups.append(blocked + sprint_rows("S5", 5, points_each=3, count=5))

    detail = BlockedClusterDetector().detect(frame_of(*groups))[0].detail

    assert detail["top_assignee"] == "alice"
    assert detail["top_assignee_blocked"] == 4
    assert detail["concentration"] == 0.8


def test_a_couple_of_blocked_issues_is_not_a_cluster():
    groups = [sprint_rows(f"S{i}", i, points_each=3, count=10) for i in range(5)]
    groups.append(
        sprint_rows("S5", 5, points_each=3, count=2, status="Blocked")
        + sprint_rows("S5", 5, points_each=3, count=8)
    )

    assert BlockedClusterDetector().detect(frame_of(*groups)) == []


# --- orchestration and scoring ---------------------------------------------


def test_detect_all_returns_findings_in_sprint_order():
    groups = steady_project(5)
    groups.append(sprint_rows("S5", 5, points_each=1, count=5))

    found = detect_all(frame_of(*groups))

    assert [a.sprint_sequence for a in found] == sorted(a.sprint_sequence for a in found)


def test_findings_are_json_serialisable():
    import json

    groups = steady_project(5)
    groups.append(sprint_rows("S5", 5, points_each=1, count=5))

    payload = json.dumps([a.to_dict() for a in detect_all(frame_of(*groups))])

    assert VELOCITY_DROP in payload


def test_scoring_requires_both_sprint_and_type_to_match():
    from app.services.anomaly.base import DetectedAnomaly

    manifest = {"anomalies": [{"sprint": "S5", "type": VELOCITY_DROP}]}
    right_sprint_wrong_type = [
        DetectedAnomaly("S5", 5, OVERDUE_PILEUP, 0.5, {})
    ]

    score = score_detections(right_sprint_wrong_type, manifest)

    assert score.overall.true_positives == 0
    assert score.overall.false_positives == 1
    assert score.overall.false_negatives == 1


def test_perfect_detection_scores_one():
    from app.services.anomaly.base import DetectedAnomaly

    manifest = {"anomalies": [{"sprint": "S5", "type": BLOCKED_CLUSTER}]}

    score = score_detections([DetectedAnomaly("S5", 5, BLOCKED_CLUSTER, 1.0, {})], manifest)

    assert score.overall.f1 == 1.0


# --- against the generator -------------------------------------------------


def test_all_injected_anomalies_are_found(generated_csv_bytes, generated_manifest):
    from app.services.ingestion import ingest

    frame = ensure_frame(ingest(generated_csv_bytes, "fixture.csv").frame)

    score = score_detections(detect_all(frame), generated_manifest)

    # FR-C1's acceptance criterion is recall > 0.7 on the synthetic set.
    assert score.overall.recall is not None and score.overall.recall > 0.7
    assert score.missed == []


def test_velocity_drop_sprint_is_not_reported_as_an_overdue_pileup(
    generated_csv_bytes, generated_manifest
):
    """Regression: a stalled sprint has the highest overdue *share* by
    construction, so a ratio-based detector flagged it and missed the real
    pileup. The signal is lateness, not volume.
    """
    from app.services.ingestion import ingest

    frame = ensure_frame(ingest(generated_csv_bytes, "fixture.csv").frame)
    found = detect_all(frame)

    drops = {a.sprint for a in found if a.anomaly_type == VELOCITY_DROP}
    pileups = {a.sprint for a in found if a.anomaly_type == OVERDUE_PILEUP}

    assert drops
    assert pileups
    assert not (drops & pileups)
