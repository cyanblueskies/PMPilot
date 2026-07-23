"""FR-D2 / FR-D3 — executive summary and management recommendations.

Both run over the deterministic track's output only. The strategy is chosen at
call time so FR-D5 can put the two arms side by side on identical data.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from app.services.analytics.pipeline import ProjectAnalysis
from app.services.llm.client import LlmResult, generate
from app.services.llm.strategies import GROUNDED, get_strategy

SUMMARY_QUESTION = (
    "Write an executive summary of this project's current health. Cover "
    "delivery pace, how long work takes to complete, quality, and any "
    "anomalies detected. State plainly if something could not be measured."
)

RECOMMENDATION_QUESTION = (
    "Based on this project's metrics and detected anomalies, give the delivery "
    "lead a short list of concrete actions to take next. For each one, name the "
    "specific evidence that motivates it. Do not suggest anything the data does "
    "not support, and say so if the data does not indicate a clear action."
)


@dataclass
class GeneratedNarrative:
    summary: LlmResult
    recommendations: LlmResult

    @property
    def ok(self) -> bool:
        return self.summary.ok and self.recommendations.ok


def _payload_for(strategy_name: str, analysis: ProjectAnalysis) -> dict:
    """What the model is allowed to see.

    The grounded arm gets the analysis without per-day burndown points: several
    hundred data points would crowd out the figures it is meant to reason about.
    The naive arm gets no analysis at all — raw rows instead — which is the
    whole point of the comparison.
    """
    return analysis.to_dict(include_series=False)


def generate_summary(
    session: Session,
    analysis: ProjectAnalysis,
    frame: pd.DataFrame,
    *,
    strategy_name: str = GROUNDED,
    question: str = SUMMARY_QUESTION,
) -> LlmResult:
    """FR-D2 — a grounded executive summary."""
    strategy = get_strategy(strategy_name)
    payload = strategy.build(question, _payload_for(strategy_name, analysis), frame)

    return generate(
        session,
        payload,
        project_id=analysis.project_id or None,
        question=question,
    )


def generate_recommendations(
    session: Session,
    analysis: ProjectAnalysis,
    frame: pd.DataFrame,
    *,
    strategy_name: str = GROUNDED,
) -> LlmResult:
    """FR-D3 — actions derived from the same evidence."""
    strategy = get_strategy(strategy_name)
    payload = strategy.build(
        RECOMMENDATION_QUESTION, _payload_for(strategy_name, analysis), frame
    )

    return generate(
        session,
        payload,
        project_id=analysis.project_id or None,
        question=RECOMMENDATION_QUESTION,
    )


def generate_narrative(
    session: Session,
    analysis: ProjectAnalysis,
    frame: pd.DataFrame,
    *,
    strategy_name: str = GROUNDED,
) -> GeneratedNarrative:
    """Summary and recommendations together, as a report needs both."""
    return GeneratedNarrative(
        summary=generate_summary(session, analysis, frame, strategy_name=strategy_name),
        recommendations=generate_recommendations(
            session, analysis, frame, strategy_name=strategy_name
        ),
    )
