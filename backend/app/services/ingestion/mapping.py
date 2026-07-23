"""FR-A2 — map varying Jira export headers to the internal schema.

Column names differ between Jira instances, versions, and export settings
("Issue key", "Issue Key", "Key" all occur). Mapping happens here, at the
ingestion boundary, so nothing downstream ever depends on a particular
export's header text (.claude/rules/data-model.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Internal field -> header spellings seen in the wild. Compared after
# normalisation, so case and separator differences need no entry here.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "issue_key": ("issue key", "key", "issue id", "issueid"),
    "issue_type": ("issue type", "type", "issuetype"),
    "status": ("status", "issue status"),
    "assignee": ("assignee", "assigned to", "owner"),
    "reporter": ("reporter", "created by", "creator"),
    "priority": ("priority",),
    "story_points": (
        "story points",
        "story point",
        "story point estimate",
        "points",
        "custom field story points",
    ),
    "sprint": ("sprint", "sprint name", "iteration"),
    "created_date": ("created date", "created", "created at"),
    # When work began, as distinct from when the issue was raised. Standard Jira
    # CSV exports usually omit it (it lives in the status-change history), so
    # cycle time degrades gracefully when it is absent.
    "started_date": (
        "in progress date",
        "started date",
        "started",
        "start date",
        "work started",
    ),
    "resolved_date": ("resolved date", "resolved", "resolution date", "done date"),
    "due_date": ("due date", "due", "duedate"),
    "labels": ("labels", "label", "tags"),
    "epic_link": ("epic link", "epic", "parent", "parent link"),
    "original_estimate": (
        "original estimate",
        "originalestimate",
        "estimate",
        "time estimate",
    ),
    "time_spent": ("time spent", "timespent", "logged time", "time logged"),
    "description": ("description", "summary description"),
    "comments": ("comments", "comment"),
}

# Without these the analytics engine cannot produce anything at all: no key
# means no identity, no status means velocity is undefined, no sprint means
# there is nothing to group by.
REQUIRED_FIELDS = ("issue_key", "status", "sprint")

# Missing these does not stop ingestion, but some KPIs become unavailable.
# Reported back so the user learns it here rather than from an empty chart.
FIELD_ENABLES: dict[str, str] = {
    "story_points": "velocity, scope creep",
    "created_date": "lead time",
    "started_date": "cycle time",
    "resolved_date": "cycle time, lead time",
    "due_date": "overdue detection",
    "issue_type": "defect density",
    "assignee": "workload distribution, blocked-task clustering",
}


class MissingRequiredFields(ValueError):
    """Raised when a required column cannot be found in the upload."""

    def __init__(self, missing: list[str], available: list[str]) -> None:
        self.missing = missing
        self.available = available
        super().__init__(
            "Could not find required column(s): "
            + ", ".join(missing)
            + ". Columns present in the file: "
            + (", ".join(available) if available else "(none)")
        )


@dataclass
class MappingResult:
    # header in the file -> internal field name
    column_map: dict[str, str]
    unmapped_columns: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    degraded_kpis: list[str] = field(default_factory=list)


def normalise_header(header: str) -> str:
    """Fold a header to its comparison form.

    Lowercases, strips Jira's custom-field bracket suffix, and collapses any
    run of non-alphanumerics to a single space, so "Story Points",
    "story_points" and "Custom field (Story Points)" all converge.
    """
    text = header.strip().lower()
    text = re.sub(r"\(([^)]*)\)", r" \1 ", text)  # unwrap "(Story Points)"
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def map_columns(headers: list[str]) -> MappingResult:
    """Match file headers to internal fields.

    Raises MissingRequiredFields if a required field has no match, with the
    available columns listed — a bare "missing column" tells the user nothing
    about what their file actually contains (FR-A2 acceptance criterion).
    """
    lookup: dict[str, str] = {}
    for internal, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            lookup[normalise_header(alias)] = internal

    column_map: dict[str, str] = {}
    unmapped: list[str] = []

    for header in headers:
        internal = lookup.get(normalise_header(header))
        # First match wins: a Jira export can carry two columns that normalise
        # alike (e.g. "Sprint" repeated per sprint the issue belonged to), and
        # silently overwriting would keep the last rather than the first.
        if internal is not None and internal not in column_map.values():
            column_map[header] = internal
        elif internal is None:
            unmapped.append(header)

    mapped = set(column_map.values())

    missing_required = [f for f in REQUIRED_FIELDS if f not in mapped]
    if missing_required:
        raise MissingRequiredFields(missing_required, list(headers))

    missing_optional = [f for f in FIELD_ALIASES if f not in mapped]
    degraded = sorted(
        {FIELD_ENABLES[f] for f in missing_optional if f in FIELD_ENABLES}
    )

    return MappingResult(
        column_map=column_map,
        unmapped_columns=unmapped,
        missing_optional=missing_optional,
        degraded_kpis=degraded,
    )
