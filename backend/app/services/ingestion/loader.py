"""FR-A1 / FR-A3 — read an upload and normalise it to the internal schema.

Upload is the only untrusted input path into the system, so the caps below are
enforced before parsing rather than after (.claude/rules/security.md). Nothing
from the file is ever executed or evaluated — spreadsheet formulas are read as
the text they are.

pandas 3.x: Copy-on-Write is mandatory here. Every transformation assigns a
result; none mutates a slice in place, which would silently do nothing
(.claude/rules/code-style.md).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from app.services.ingestion.mapping import MappingResult, map_columns

ALLOWED_EXTENSIONS = (".csv", ".xlsx")

# The spec designs for 500-5,000 issues per project. The caps sit well above
# that so a legitimate large export is not rejected, while a file that could
# exhaust memory is refused before pandas ever sees all of it.
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_ROWS = 20_000

DATE_FIELDS = ("created_date", "started_date", "resolved_date", "due_date")
NUMERIC_FIELDS = ("story_points", "original_estimate", "time_spent")
TEXT_FIELDS = (
    "issue_key",
    "issue_type",
    "status",
    "assignee",
    "reporter",
    "priority",
    "sprint",
    "labels",
    "epic_link",
    "description",
    "comments",
)


class UploadRejected(ValueError):
    """The upload cannot be accepted. The message is safe to show a user."""


@dataclass
class IngestResult:
    frame: pd.DataFrame
    mapping: MappingResult
    row_count: int
    # Values that could not be parsed, per field. Surfaced rather than hidden:
    # a column that silently became all-NaT would quietly disable a KPI.
    unparsed: dict[str, int] = field(default_factory=dict)
    dropped_rows: int = 0


def _read_frame(content: bytes, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise UploadRejected(
            f"Unsupported file type. Upload a {' or '.join(ALLOWED_EXTENSIONS)} file."
        )

    if len(content) > MAX_FILE_BYTES:
        raise UploadRejected(
            f"File is too large ({len(content) // 1024 // 1024} MB). "
            f"The limit is {MAX_FILE_BYTES // 1024 // 1024} MB."
        )
    if not content.strip():
        raise UploadRejected("File is empty.")

    # nrows caps the parse itself, so an oversized row count costs one row of
    # memory to detect rather than the whole file.
    try:
        if lower.endswith(".csv"):
            frame = pd.read_csv(
                io.BytesIO(content), nrows=MAX_ROWS + 1, encoding_errors="replace"
            )
        else:
            frame = pd.read_excel(io.BytesIO(content), nrows=MAX_ROWS + 1)
    except UploadRejected:
        raise
    except Exception as exc:
        # Never surface a parser traceback to the client.
        raise UploadRejected(
            f"Could not read the file: {type(exc).__name__}. "
            "Check that it is a valid, uncorrupted CSV or XLSX export."
        ) from exc

    if len(frame) > MAX_ROWS:
        raise UploadRejected(
            f"File has more than {MAX_ROWS:,} rows. Split it into smaller exports."
        )
    if frame.empty:
        raise UploadRejected("File contains headers but no data rows.")

    return frame


def _clean_text(series: pd.Series) -> pd.Series:
    """Trim, collapse internal whitespace, and turn blanks into NA."""
    cleaned = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    return cleaned.replace("", pd.NA)


def ingest(content: bytes, filename: str) -> IngestResult:
    """Parse an upload into the internal schema.

    Raises UploadRejected with a user-safe message on any failure.
    """
    raw = _read_frame(content, filename)
    mapping = map_columns(list(raw.columns))

    frame = raw.rename(columns=mapping.column_map)
    frame = frame[list(mapping.column_map.values())]

    unparsed: dict[str, int] = {}

    for column in TEXT_FIELDS:
        if column in frame.columns:
            frame[column] = _clean_text(frame[column])

    for column in DATE_FIELDS:
        if column not in frame.columns:
            continue
        # utc=True is not optional: Jira exports carry offsets, and cycle time
        # is computed by subtraction. A naive datetime shifts every duration
        # KPI by hours with no error anywhere.
        parsed = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
        had_value = frame[column].notna()
        unparsed[column] = int((had_value & parsed.isna()).sum())
        frame[column] = parsed

    for column in NUMERIC_FIELDS:
        if column not in frame.columns:
            continue
        # Blank stays NA rather than becoming 0. An unestimated issue is not a
        # zero-point issue, and conflating them understates velocity.
        parsed = pd.to_numeric(frame[column], errors="coerce")
        had_value = frame[column].notna()
        unparsed[column] = int((had_value & parsed.isna()).sum())
        frame[column] = parsed

    before = len(frame)
    # A row with no issue key cannot be identified, referenced, or deduplicated.
    frame = frame[frame["issue_key"].notna()]
    frame = frame.drop_duplicates(subset="issue_key", keep="first")
    frame = frame.reset_index(drop=True)

    if frame.empty:
        raise UploadRejected(
            "No usable rows: every row is missing an issue key."
        )

    return IngestResult(
        frame=frame,
        mapping=mapping,
        row_count=len(frame),
        unparsed={k: v for k, v in unparsed.items() if v},
        dropped_rows=before - len(frame),
    )
