"""Claude client with mandatory call logging.

Every call writes a `query_logs` row before returning. That row is the
experiment's primary data, not a debug log: hallucination rate is scored after
the fact by checking each number in `raw_response` against `grounding_payload`.
Storing only the answer text makes the metric permanently uncomputable
(.claude/rules/experiment.md).

The model id and effort are read from config and never chosen at a call site.
Changing either partway through the project makes the grounded and naive arms
incomparable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.llm import QueryLog
from app.services.llm.strategies import PromptPayload

# temperature / top_p / top_k do not exist on this model family and are
# rejected with a 400. Determinism comes from the pinned model id plus full
# call logging, not from sampling parameters.
MAX_TOKENS = 4096


class LlmUnavailable(RuntimeError):
    """The generative track could not answer. Never raised into a core view."""


@dataclass
class LlmResult:
    text: str
    model_id: str
    strategy: str
    latency_ms: int
    query_log_id: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _build_client():
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LlmUnavailable("ANTHROPIC_API_KEY is not set.")

    from anthropic import Anthropic

    return Anthropic(api_key=settings.anthropic_api_key)


def _log(
    session: Session,
    *,
    project_id: int | None,
    question: str | None,
    payload: PromptPayload,
    response_text: str | None,
    latency_ms: int,
    error: str | None,
    generated_sql: str | None = None,
) -> int:
    """Write the query_logs row. Called on both success and failure."""
    settings = get_settings()
    row = QueryLog(
        project_id=project_id,
        question=question,
        raw_prompt=f"{payload.system}\n\n---\n\n{payload.user}",
        raw_response=response_text,
        model_id=settings.anthropic_model_id,
        prompting_strategy=payload.strategy,
        effort=settings.anthropic_effort,
        grounding_payload=payload.grounding_payload,
        generated_sql=generated_sql,
        latency_ms=latency_ms,
        error=error,
    )
    session.add(row)
    session.flush()
    return row.id


def generate(
    session: Session,
    payload: PromptPayload,
    *,
    project_id: int | None = None,
    question: str | None = None,
    generated_sql: str | None = None,
) -> LlmResult:
    """Send a prompt and record the exchange. Caller owns the commit.

    A failure is returned rather than raised, and is logged either way: a call
    that errored is still evidence about the experiment, and the caller's job is
    to degrade gracefully rather than propagate.
    """
    settings = get_settings()
    started = time.perf_counter()

    try:
        client = _build_client()
        response = client.messages.create(
            model=settings.anthropic_model_id,
            max_tokens=MAX_TOKENS,
            system=payload.system,
            messages=[{"role": "user", "content": payload.user}],
            output_config={"effort": settings.anthropic_effort},
            thinking={"type": "adaptive"},
        )
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        error = None
    except Exception as exc:  # noqa: BLE001 - any failure must still be logged
        text = None
        error = f"{type(exc).__name__}: {exc}"

    latency_ms = int((time.perf_counter() - started) * 1000)

    log_id = _log(
        session,
        project_id=project_id,
        question=question,
        payload=payload,
        response_text=text,
        latency_ms=latency_ms,
        error=error,
        generated_sql=generated_sql,
    )

    return LlmResult(
        text=text or "",
        model_id=settings.anthropic_model_id,
        strategy=payload.strategy,
        latency_ms=latency_ms,
        query_log_id=log_id,
        error=error,
    )
