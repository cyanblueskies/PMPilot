"""FR-B3 — cycle time and lead time.

Cycle time runs from work starting; lead time from the issue being raised. They
are deliberately separate metrics: reporting one under the other's name makes
the number wrong in a way nobody can see.
"""

import pandas as pd
import pytest

from app.services.analytics import (
    compute_cycle_time,
    compute_lead_time,
    ensure_frame,
)

DAY = pd.Timedelta(days=1)
BASE = pd.Timestamp("2026-01-05T09:00:00Z")


def make_frame(rows: list[dict]) -> pd.DataFrame:
    return ensure_frame(pd.DataFrame(rows))


def issue(key, created_days=0, started_days=None, resolved_days=None, status="Done"):
    return {
        "issue_key": key,
        "status": status,
        "sprint": "Sprint 1",
        "sprint_sequence": 0,
        "created_date": BASE + created_days * DAY,
        "started_date": None if started_days is None else BASE + started_days * DAY,
        "resolved_date": None if resolved_days is None else BASE + resolved_days * DAY,
    }


# --- the two metrics are distinct ------------------------------------------


def test_cycle_time_measures_from_work_starting():
    # created day 0, started day 2, resolved day 6 -> cycle 4 days
    frame = make_frame([issue("PM-1", 0, 2, 6)])

    assert compute_cycle_time(frame).mean_days == 4


def test_lead_time_measures_from_creation():
    # created day 0, started day 2, resolved day 6 -> lead 6 days
    frame = make_frame([issue("PM-1", 0, 2, 6)])

    assert compute_lead_time(frame).mean_days == 6


def test_cycle_time_is_never_greater_than_lead_time():
    frame = make_frame([issue("PM-1", 0, 3, 10), issue("PM-2", 0, 1, 4)])

    assert compute_cycle_time(frame).mean_days < compute_lead_time(frame).mean_days


# --- availability ----------------------------------------------------------


def test_cycle_time_is_unavailable_without_started_dates():
    """Absent timestamps must not silently degrade into lead time."""
    frame = make_frame([issue("PM-1", 0, None, 6)])

    report = compute_cycle_time(frame)

    assert report.available is False
    assert report.mean_days is None
    assert "started_date" in report.unavailable_reason


def test_lead_time_still_works_when_started_dates_are_absent():
    frame = make_frame([issue("PM-1", 0, None, 6)])

    assert compute_lead_time(frame).available is True
    assert compute_lead_time(frame).mean_days == 6


def test_unavailable_is_distinct_from_no_completed_work():
    """"Cannot be measured" and "nothing finished yet" are different answers."""
    frame = make_frame([issue("PM-1", 0, 1, None, status="In Progress")])

    report = compute_cycle_time(frame)

    assert report.available is True
    assert report.sample_size == 0


# --- statistics ------------------------------------------------------------


def test_only_completed_issues_contribute():
    frame = make_frame(
        [
            issue("PM-1", 0, 1, 3),
            issue("PM-2", 0, 1, 99, status="In Progress"),
        ]
    )

    assert compute_cycle_time(frame).sample_size == 1


def test_median_and_p85_are_hand_checkable():
    # cycle times 1..10 days -> median 5.5, p85 8.65
    frame = make_frame([issue(f"PM-{d}", 0, 0, d) for d in range(1, 11)])

    report = compute_cycle_time(frame)

    assert report.sample_size == 10
    assert report.median_days == 5.5
    assert report.p85_days == pytest.approx(8.65, abs=0.01)


def test_negative_durations_are_excluded_not_averaged_in():
    """Resolved-before-started is contradictory data, not a fast delivery."""
    frame = make_frame([issue("PM-1", 0, 5, 2), issue("PM-2", 0, 0, 4)])

    report = compute_cycle_time(frame)

    assert report.sample_size == 1
    assert report.mean_days == 4


def test_duration_report_is_json_serialisable():
    import json

    frame = make_frame([issue("PM-1", 0, 1, 3)])

    assert '"metric": "cycle_time"' in json.dumps(compute_cycle_time(frame).to_dict())


# --- against real generated data -------------------------------------------


def test_generated_dataset_supports_both_metrics(generated_csv_bytes):
    from app.services.ingestion import ingest

    frame = ensure_frame(ingest(generated_csv_bytes, "fixture.csv").frame)

    cycle = compute_cycle_time(frame)
    lead = compute_lead_time(frame)

    assert cycle.available and lead.available
    assert cycle.sample_size == lead.sample_size
    # The generator places work start strictly after creation, so cycle time
    # must come out shorter across the whole dataset.
    assert cycle.mean_days < lead.mean_days


def test_export_without_started_column_degrades_cycle_time_only(generated_csv_bytes):
    """A realistic Jira export lacks the column; lead time must still work."""
    from app.services.ingestion import ingest

    frame = ensure_frame(ingest(generated_csv_bytes, "fixture.csv").frame)
    frame["started_date"] = pd.NaT

    assert compute_cycle_time(frame).available is False
    assert compute_lead_time(frame).available is True
