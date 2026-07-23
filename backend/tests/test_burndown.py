"""FR-B2 — burndown and burnup.

Acceptance criterion is that chart data points agree with the source data, so
every expectation here is computed by hand from the rows in the test.
"""

import pandas as pd

from app.services.analytics import compute_burndown, ensure_frame

DAY = pd.Timedelta(days=1)
START = pd.Timestamp("2026-01-05T00:00:00Z")


def make_frame(rows: list[dict]) -> pd.DataFrame:
    return ensure_frame(pd.DataFrame(rows))


def issue(key, points, created_day=0, resolved_day=None, status="Done", sprint="S1", seq=0):
    return {
        "issue_key": key,
        "status": status,
        "story_points": points,
        "sprint": sprint,
        "sprint_sequence": seq,
        "created_date": START + created_day * DAY,
        "resolved_date": None if resolved_day is None else START + resolved_day * DAY,
        "due_date": START + 4 * DAY,
    }


def test_remaining_falls_as_work_is_resolved():
    # 10 points total: 4 resolved on day 1, 6 on day 3.
    frame = make_frame(
        [
            issue("PM-1", 4, created_day=0, resolved_day=1),
            issue("PM-2", 6, created_day=0, resolved_day=3),
        ]
    )

    points = compute_burndown(frame).sprints[0].points
    remaining = {p.date: p.remaining_points for p in points}

    assert remaining["2026-01-05"] == 10  # nothing resolved yet
    assert remaining["2026-01-06"] == 6  # PM-1 done
    assert remaining["2026-01-08"] == 0  # both done


def test_completed_series_is_cumulative():
    frame = make_frame(
        [
            issue("PM-1", 4, resolved_day=1),
            issue("PM-2", 6, resolved_day=3),
        ]
    )

    completed = {p.date: p.completed_points for p in compute_burndown(frame).sprints[0].points}

    assert completed["2026-01-05"] == 0
    assert completed["2026-01-06"] == 4
    assert completed["2026-01-08"] == 10


def test_unfinished_work_never_burns_down():
    frame = make_frame([issue("PM-1", 8, status="In Progress")])

    sprint = compute_burndown(frame).sprints[0]

    assert sprint.completed == 0
    assert all(p.remaining_points == 8 for p in sprint.points)


def test_scope_added_mid_sprint_raises_the_scope_line():
    """Work added later must show as rising scope, not as the team slowing."""
    frame = make_frame(
        [
            issue("PM-1", 5, created_day=0, resolved_day=1),
            issue("PM-2", 7, created_day=2, resolved_day=None, status="In Progress"),
        ]
    )

    sprint = compute_burndown(frame).sprints[0]
    scope = {p.date: p.scope_points for p in sprint.points}

    assert sprint.initial_scope == 5
    assert sprint.final_scope == 12
    assert sprint.scope_added == 7
    assert scope["2026-01-05"] == 5
    assert scope["2026-01-07"] == 12


def test_ideal_line_runs_from_initial_scope_to_zero():
    frame = make_frame([issue("PM-1", 10, resolved_day=4)])

    points = compute_burndown(frame).sprints[0].points

    assert points[0].ideal_remaining == 10
    assert points[-1].ideal_remaining == 0
    # Monotonically non-increasing.
    values = [p.ideal_remaining for p in points]
    assert values == sorted(values, reverse=True)


def test_unestimated_issues_contribute_nothing_to_the_series():
    frame = make_frame([issue("PM-1", 5, resolved_day=1), issue("PM-2", None, resolved_day=1)])

    sprint = compute_burndown(frame).sprints[0]

    assert sprint.final_scope == 5
    assert sprint.completed == 5


def test_sprints_are_reported_in_sequence_order():
    frame = make_frame(
        [
            issue("PM-1", 5, sprint="Sprint 10", seq=1),
            issue("PM-2", 3, sprint="Sprint 2", seq=0),
        ]
    )

    assert [s.sprint for s in compute_burndown(frame).sprints] == ["Sprint 2", "Sprint 10"]


def test_burndown_is_unavailable_without_creation_dates():
    frame = make_frame([{"issue_key": "PM-1", "status": "Done", "sprint": "S1", "sprint_sequence": 0}])

    report = compute_burndown(frame)

    assert report.available is False
    assert "created_date" in report.unavailable_reason


def test_empty_frame_is_unavailable_not_an_error():
    assert compute_burndown(make_frame([])).available is False


def test_report_is_json_serialisable():
    import json

    frame = make_frame([issue("PM-1", 5, resolved_day=1)])

    assert '"remaining_points"' in json.dumps(compute_burndown(frame).to_dict())


def test_generated_dataset_produces_one_series_per_sprint(generated_csv_bytes):
    from app.services.ingestion import ingest

    frame = ensure_frame(ingest(generated_csv_bytes, "fixture.csv").frame)
    report = compute_burndown(frame)

    assert report.available
    assert len(report.sprints) == frame["sprint"].nunique()
    for sprint in report.sprints:
        assert sprint.points
        # Final completed value in the series must agree with the sprint total.
        assert sprint.points[-1].completed_points == sprint.completed
