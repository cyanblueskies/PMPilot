"""API contract for dataset upload.

Pydantic schemas are the contract; ORM objects are never returned directly
(.claude/rules/data-model.md).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UploadAccepted(BaseModel):
    """Returned once the file has parsed and persistence has been scheduled."""

    project_id: int
    name: str
    status: str
    row_count: int = Field(description="Usable rows found in the upload")
    dropped_rows: int = Field(
        default=0, description="Rows discarded as duplicates or missing an issue key"
    )
    unmapped_columns: list[str] = Field(
        default_factory=list,
        description="Columns in the file that matched no known field",
    )
    missing_optional_fields: list[str] = Field(
        default_factory=list,
        description="Recognised fields absent from the file",
    )
    degraded_kpis: list[str] = Field(
        default_factory=list,
        description="KPIs unavailable because of the missing fields above",
    )
    unparsed_values: dict[str, int] = Field(
        default_factory=dict,
        description="Count of values that could not be parsed, by field",
    )


class ProjectStatus(BaseModel):
    project_id: int
    name: str
    status: str
    issue_count: int
    error: str | None = None
    created_at: datetime
