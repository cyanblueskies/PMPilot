"""Generative track.

Receives the deterministic track's output only — never raw issue tables — with
the single exception of the FR-D5 naive baseline, which sends raw rows by
design so the grounded arm has something to be measured against.
"""

from app.services.llm.client import LlmResult, LlmUnavailable, generate
from app.services.llm.strategies import (
    GROUNDED,
    NAIVE,
    GroundedStrategy,
    NaiveStrategy,
    PromptPayload,
    PromptStrategy,
    get_strategy,
)

__all__ = [
    "generate",
    "LlmResult",
    "LlmUnavailable",
    "get_strategy",
    "GroundedStrategy",
    "NaiveStrategy",
    "PromptStrategy",
    "PromptPayload",
    "GROUNDED",
    "NAIVE",
]
