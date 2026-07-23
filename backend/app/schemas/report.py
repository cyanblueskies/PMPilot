"""API contract for report generation and retrieval."""

from datetime import datetime

from pydantic import BaseModel, Field


class ReportRequested(BaseModel):
    report_id: int
    project_id: int
    status: str
    prompting_strategy: str


class ReportOut(BaseModel):
    report_id: int
    project_id: int
    title: str
    content: str
    prompting_strategy: str | None = None
    created_at: datetime
    # Points at the query_logs rows this report came from, so any figure in the
    # text can be traced back to the exact prompt and payload that produced it.
    query_log_id: int | None = None


class ReportSummary(BaseModel):
    report_id: int
    title: str
    prompting_strategy: str | None = None
    created_at: datetime


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class QueryEvidence(BaseModel):
    generated_sql: str | None = None
    row_count: int = 0
    rows: list[dict] = Field(default_factory=list)


class QueryResponse(BaseModel):
    question: str
    answer: str
    in_scope: bool
    evidence: QueryEvidence | None = None
    query_log_id: int | None = None
    refusal_reason: str | None = None
