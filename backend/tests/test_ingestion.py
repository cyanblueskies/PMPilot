"""Ingestion and field mapping.

Runs offline against in-memory CSV bytes — no database, no network.
"""

import pandas as pd
import pytest

from app.services.ingestion import (
    MAX_ROWS,
    MissingRequiredFields,
    UploadRejected,
    ingest,
    map_columns,
    normalise_header,
)

MINIMAL = b"Issue Key,Status,Sprint\nPM-1,Done,Sprint 1\n"


def csv_bytes(header: str, *rows: str) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


# --- field mapping (FR-A2) -------------------------------------------------


def test_header_variants_map_to_the_same_field():
    for spelling in ["Issue Key", "issue_key", "ISSUE KEY", "Key", "issue-key"]:
        result = map_columns([spelling, "Status", "Sprint"])
        assert result.column_map[spelling] == "issue_key"


def test_jira_custom_field_wrapper_is_unwrapped():
    assert normalise_header("Custom field (Story Points)") == "custom field story points"

    result = map_columns(["Issue Key", "Status", "Sprint", "Custom field (Story Points)"])
    assert "story_points" in result.column_map.values()


def test_missing_required_field_names_what_is_missing_and_what_is_present():
    with pytest.raises(MissingRequiredFields) as exc:
        map_columns(["Issue Key", "Status"])

    assert exc.value.missing == ["sprint"]
    assert "Issue Key" in str(exc.value)


def test_duplicate_headers_keep_the_first_match():
    result = map_columns(["Issue Key", "Status", "Sprint", "Sprint Name"])

    assert list(result.column_map.values()).count("sprint") == 1
    assert result.column_map["Sprint"] == "sprint"


def test_missing_optional_fields_report_which_kpis_degrade():
    result = map_columns(["Issue Key", "Status", "Sprint"])

    assert "story_points" in result.missing_optional
    assert any("velocity" in k for k in result.degraded_kpis)


def test_unrecognised_columns_are_reported_not_silently_dropped():
    result = map_columns(["Issue Key", "Status", "Sprint", "Some Custom Thing"])

    assert result.unmapped_columns == ["Some Custom Thing"]


# --- parsing and cleaning (FR-A1 / FR-A3) ----------------------------------


def test_mixed_timezone_offsets_all_normalise_to_utc():
    content = csv_bytes(
        "Issue Key,Status,Sprint,Created Date",
        "PM-1,Done,Sprint 1,2026-01-05T09:00:00+00:00",
        "PM-2,Done,Sprint 1,2026-01-05T17:00:00+08:00",
        "PM-3,Done,Sprint 1,2026-01-05T04:00:00-05:00",
    )

    frame = ingest(content, "export.csv").frame

    assert str(frame["created_date"].dt.tz) == "UTC"
    # All three describe the same instant; after normalisation they must agree.
    assert frame["created_date"].nunique() == 1


def test_blank_story_points_stay_missing_and_do_not_become_zero():
    content = csv_bytes(
        "Issue Key,Status,Sprint,Story Points",
        "PM-1,Done,Sprint 1,5",
        "PM-2,Done,Sprint 1,",
    )

    frame = ingest(content, "export.csv").frame

    assert frame.loc[0, "story_points"] == 5
    assert pd.isna(frame.loc[1, "story_points"])
    assert frame["story_points"].sum() == 5


def test_whitespace_is_trimmed_and_blanks_become_missing():
    content = csv_bytes(
        "Issue Key,Status,Sprint,Assignee",
        "  PM-1  ,Done,Sprint 1,  Alice   Smith  ",
        "PM-2,Done,Sprint 1,   ",
    )

    frame = ingest(content, "export.csv").frame

    assert frame.loc[0, "issue_key"] == "PM-1"
    assert frame.loc[0, "assignee"] == "Alice Smith"
    assert pd.isna(frame.loc[1, "assignee"])


def test_unparseable_dates_are_counted_rather_than_hidden():
    content = csv_bytes(
        "Issue Key,Status,Sprint,Created Date",
        "PM-1,Done,Sprint 1,2026-01-05T09:00:00+00:00",
        "PM-2,Done,Sprint 1,not a date",
    )

    result = ingest(content, "export.csv")

    assert result.unparsed["created_date"] == 1
    assert pd.isna(result.frame.loc[1, "created_date"])


def test_duplicate_issue_keys_are_deduplicated():
    content = csv_bytes(
        "Issue Key,Status,Sprint",
        "PM-1,Done,Sprint 1",
        "PM-1,In Progress,Sprint 1",
        "PM-2,Done,Sprint 1",
    )

    result = ingest(content, "export.csv")

    assert result.row_count == 2
    assert result.dropped_rows == 1
    assert result.frame.loc[0, "status"] == "Done"  # first wins


def test_rows_without_an_issue_key_are_dropped():
    content = csv_bytes(
        "Issue Key,Status,Sprint",
        "PM-1,Done,Sprint 1",
        ",Done,Sprint 1",
    )

    result = ingest(content, "export.csv")

    assert result.row_count == 1
    assert result.dropped_rows == 1


# --- rejection paths (security.md) -----------------------------------------


def test_unsupported_extension_is_rejected():
    with pytest.raises(UploadRejected, match="Unsupported file type"):
        ingest(MINIMAL, "export.txt")


def test_oversized_file_is_rejected():
    with pytest.raises(UploadRejected, match="too large"):
        ingest(b"x" * (21 * 1024 * 1024), "export.csv")


def test_too_many_rows_is_rejected():
    rows = [f"PM-{i},Done,Sprint 1" for i in range(MAX_ROWS + 5)]
    with pytest.raises(UploadRejected, match="more than"):
        ingest(csv_bytes("Issue Key,Status,Sprint", *rows), "export.csv")


def test_empty_file_is_rejected():
    with pytest.raises(UploadRejected, match="empty"):
        ingest(b"   ", "export.csv")


def test_headers_with_no_data_rows_is_rejected():
    with pytest.raises(UploadRejected, match="no data rows"):
        ingest(b"Issue Key,Status,Sprint\n", "export.csv")


def test_corrupt_file_reports_a_message_not_a_traceback():
    with pytest.raises(UploadRejected) as exc:
        ingest(b"PK\x03\x04garbage-not-really-xlsx", "export.xlsx")

    message = str(exc.value)
    assert "Could not read the file" in message
    assert "Traceback" not in message


def test_spreadsheet_formulas_are_read_as_text_not_evaluated():
    content = csv_bytes(
        "Issue Key,Status,Sprint,Description",
        "PM-1,Done,Sprint 1,=1+1",
    )

    frame = ingest(content, "export.csv").frame

    assert frame.loc[0, "description"] == "=1+1"


# --- against the FR-A4 generator -------------------------------------------


def test_generated_dataset_ingests_cleanly(generated_csv_bytes):
    """The generator's output must be accepted by the real ingestion path.

    If these two ever drift, every downstream KPI and detection test is
    running on data the system could not actually accept.
    """
    result = ingest(generated_csv_bytes, "demo.csv")

    assert result.row_count > 0
    assert result.mapping.missing_optional == []
    assert result.unparsed == {}
    assert str(result.frame["created_date"].dt.tz) == "UTC"
