"""FR-B1 / FR-B4 — velocity and defect density.

Expected values are hand-calculated in each test so a regression shows up as a
disagreement with arithmetic, not with a previous run of the same code.
"""

import pandas as pd
import pytest

from app.services.analytics import (
    compute_defect_density,
    compute_velocity,
    ensure_frame,
)


def make_frame(rows: list[dict]) -> pd.DataFrame:
    return ensure_frame(pd.DataFrame(rows))


def issue(key, status="Done", points=None, sprint="Sprint 1", type_="Story", seq=0):
    return {
        "issue_key": key,
        "status": status,
        "story_points": points,
        "sprint": sprint,
        "sprint_sequence": seq,
        "issue_type": type_,
    }


# --- FR-B1 velocity --------------------------------------------------------


def test_velocity_counts_only_completed_issues():
    # 5 + 3 done, 8 in progress -> 8
    frame = make_frame(
        [
            issue("PM-1", "Done", 5),
            issue("PM-2", "Done", 3),
            issue("PM-3", "In Progress", 8),
        ]
    )

    report = compute_velocity(frame)

    assert report.sprints[0].velocity == 8
    assert report.sprints[0].completed_issues == 2
    assert report.sprints[0].total_issues == 3


def test_velocity_recognises_alternative_done_statuses():
    frame = make_frame(
        [
            issue("PM-1", "Closed", 2),
            issue("PM-2", "Resolved", 3),
            issue("PM-3", "COMPLETE", 5),
        ]
    )

    assert compute_velocity(frame).sprints[0].velocity == 10


def test_unknown_status_is_treated_as_not_done():
    """Understating progress is the safe failure; overstating it is not."""
    frame = make_frame([issue("PM-1", "Awaiting Deployment", 5)])

    assert compute_velocity(frame).sprints[0].velocity == 0


def test_unestimated_completed_work_is_reported_not_counted_as_zero():
    frame = make_frame(
        [
            issue("PM-1", "Done", 5),
            issue("PM-2", "Done", None),
        ]
    )

    sprint = compute_velocity(frame).sprints[0]

    assert sprint.velocity == 5
    assert sprint.unestimated_completed == 1
    assert compute_velocity(frame).has_unestimated_work is True


def test_velocity_is_reported_per_sprint_in_sequence_order():
    frame = make_frame(
        [
            issue("PM-1", "Done", 5, sprint="Sprint 10", seq=1),
            issue("PM-2", "Done", 3, sprint="Sprint 2", seq=0),
        ]
    )

    report = compute_velocity(frame)

    assert [s.sprint for s in report.sprints] == ["Sprint 2", "Sprint 10"]
    assert [s.velocity for s in report.sprints] == [3, 5]


def test_velocity_summary_statistics_are_hand_checkable():
    # velocities 10, 20, 30 -> mean 20, median 20, sample stdev 10
    frame = make_frame(
        [
            issue("PM-1", "Done", 10, sprint="S1", seq=0),
            issue("PM-2", "Done", 20, sprint="S2", seq=1),
            issue("PM-3", "Done", 30, sprint="S3", seq=2),
        ]
    )

    report = compute_velocity(frame)

    assert report.mean == 20
    assert report.median == 20
    assert report.stdev == 10


def test_stdev_is_undefined_for_a_single_sprint():
    """One observation carries no information about spread."""
    frame = make_frame([issue("PM-1", "Done", 5)])

    assert compute_velocity(frame).stdev is None


def test_empty_frame_produces_an_empty_report_not_an_error():
    report = compute_velocity(make_frame([]))

    assert report.sprints == []
    assert report.mean is None


def test_velocity_report_is_json_serialisable():
    """This output is handed to the LLM verbatim, so it must serialise."""
    import json

    frame = make_frame([issue("PM-1", "Done", 5)])

    payload = json.dumps(compute_velocity(frame).to_dict())

    assert '"velocity": 5.0' in payload


# --- FR-B4 defect density --------------------------------------------------


def test_defect_ratio_is_bugs_over_all_issues():
    # 1 bug of 4 issues -> 0.25
    frame = make_frame(
        [
            issue("PM-1", type_="Bug"),
            issue("PM-2", type_="Story"),
            issue("PM-3", type_="Task"),
            issue("PM-4", type_="Story"),
        ]
    )

    assert compute_defect_density(frame).defect_ratio == 0.25


def test_defect_density_is_bugs_per_delivered_point():
    # 2 bugs, 10 delivered points -> 0.2
    frame = make_frame(
        [
            issue("PM-1", "Done", 5, type_="Bug"),
            issue("PM-2", "Done", 5, type_="Bug"),
            issue("PM-3", "In Progress", 8, type_="Story"),
        ]
    )

    assert compute_defect_density(frame).defect_density == 0.2


def test_defect_density_is_undefined_when_nothing_was_delivered():
    """Zero delivered points makes the ratio undefined, not zero."""
    frame = make_frame([issue("PM-1", "In Progress", 5, type_="Bug")])

    assert compute_defect_density(frame).defect_density is None
    assert compute_defect_density(frame).defect_count == 1


def test_defect_types_are_matched_case_insensitively():
    frame = make_frame([issue("PM-1", type_="bug"), issue("PM-2", type_="DEFECT")])

    assert compute_defect_density(frame).defect_count == 2


def test_defect_report_breaks_down_by_sprint():
    frame = make_frame(
        [
            issue("PM-1", type_="Bug", sprint="S1", seq=0),
            issue("PM-2", type_="Story", sprint="S1", seq=0),
            issue("PM-3", type_="Bug", sprint="S2", seq=1),
        ]
    )

    by_sprint = compute_defect_density(frame).by_sprint

    assert by_sprint[0] == {
        "sprint": "S1",
        "total_issues": 2,
        "defect_count": 1,
        "defect_ratio": 0.5,
    }
    assert by_sprint[1]["defect_ratio"] == 1.0


# --- against the generator -------------------------------------------------


def test_velocity_matches_the_generator_manifest(generated_csv_bytes, generated_manifest):
    """The engine must reproduce the velocity the generator recorded.

    Both apply the same definition (points on done issues), but by different
    code and across the whole CSV -> ingest -> frame -> KPI path. It therefore
    catches mapping, parsing, status-normalisation and grouping regressions —
    not an error in the shared definition itself.
    """
    from app.services.ingestion import ingest

    frame = ensure_frame(ingest(generated_csv_bytes, "fixture.csv").frame)

    computed = {s.sprint: s.velocity for s in compute_velocity(frame).sprints}
    expected = {k: v["velocity"] for k, v in generated_manifest["per_sprint"].items()}

    assert computed == pytest.approx(expected)
