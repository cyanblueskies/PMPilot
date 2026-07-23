"""Generative track output: LLM call log and generated reports."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now_column


class QueryLog(Base):
    """One LLM call, recorded in full.

    This is the experiment's primary data source, not a debug log. Hallucination
    rate is scored *after the fact* by checking every number in `raw_response`
    against `grounding_payload`. Storing only the final answer text makes that
    check impossible and the metric permanently uncomputable — see
    .claude/rules/experiment.md.

    Every field below is mandatory instrumentation. Do not make writes to this
    table conditional on a debug flag.
    """

    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )

    # What the user asked, where applicable (NL2SQL and chat; null for an
    # unprompted summary generation).
    question: Mapped[str | None] = mapped_column(Text)

    raw_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text)

    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # "grounded" | "naive" — the experimental condition (FR-D5).
    prompting_strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    effort: Mapped[str | None] = mapped_column(String(20))

    # The exact KPI/anomaly JSON supplied to the model. The answer key for
    # hallucination scoring. Null only for naive-mode calls, which by design
    # receive raw data instead.
    grounding_payload: Mapped[dict | None] = mapped_column(JSONB)

    # NL2SQL only: the statement the model produced, kept as an audit trail.
    generated_sql: Mapped[str | None] = mapped_column(Text)

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = utc_now_column()

    __table_args__ = (
        Index("ix_query_logs_strategy", "prompting_strategy"),
        Index("ix_query_logs_model", "model_id"),
    )


class Report(Base):
    """A generated executive summary (FR-F3), persisted for export (FR-F4)."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    query_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("query_logs.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompting_strategy: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = utc_now_column()
