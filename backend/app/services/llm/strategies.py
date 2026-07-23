"""FR-D2 / FR-D5 — prompting strategies.

Two implementations behind one interface, selected at call time. This shape
exists from the first commit so that adding the naive baseline was a new class
rather than a refactor of working code (.claude/rules/experiment.md).

**The naive strategy is the experiment, not an anti-pattern.** It sends raw
issue rows on purpose, because measuring the hallucination rate of the grounded
strategy requires something to measure it against. Never delete it, never
"clean it up", never flag it as a code smell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

GROUNDED = "grounded"
NAIVE = "naive"

# Raw rows are large. Past this many the naive prompt is truncated, and the
# truncation is stated in the prompt so the model is not silently reasoning
# about a partial table it believes is complete.
NAIVE_MAX_ROWS = 400

# Columns the naive strategy sends. Free text is excluded even here: it adds
# thousands of tokens of synthetic filler without changing what the model can
# conclude, and the comparison is about numeric grounding.
NAIVE_COLUMNS = (
    "issue_key",
    "issue_type",
    "status",
    "assignee",
    "story_points",
    "sprint",
    "created_date",
    "resolved_date",
    "due_date",
)

GROUNDED_SYSTEM = """\
You are a project management analyst. You write short, factual status \
assessments for a delivery lead.

You will be given a JSON document containing precomputed project metrics and \
detected anomalies. That document is your only source of facts.

Rules, in order of importance:

1. Every number you state must appear in the JSON you were given. Do not \
compute new figures, do not estimate, and do not round in a way that changes \
the value. If you want to express a difference or a percentage that is not \
present, describe it in words instead.
2. If the JSON does not contain something, say that it is not available. Do \
not infer it from context or from what is typical.
3. A metric marked "available": false was not measurable from the uploaded \
data. Say so plainly; do not substitute a related metric for it.
4. Refer to sprints and issues by the identifiers given in the JSON, so a \
reader can trace every claim back to the data.

Write plainly, in prose, for someone who has two minutes. Lead with what \
matters. Do not use headings unless the answer genuinely has several parts.\
"""

NAIVE_SYSTEM = """\
You are a project management analyst. You write short, factual status \
assessments for a delivery lead.

You will be given raw issue records exported from a project tracker. Analyse \
them and answer the question.

Write plainly, in prose, for someone who has two minutes. Lead with what \
matters.\
"""


@dataclass
class PromptPayload:
    """A rendered prompt, plus the ground truth it was built from."""

    system: str
    user: str
    strategy: str
    # The exact JSON supplied as fact. Hallucination rate is scored later by
    # checking every number in the response against this, so it is stored
    # rather than reconstructed. None for the naive arm, which by design
    # receives raw data instead — its claims are scored against the dataset.
    grounding_payload: dict | None = None
    metadata: dict = field(default_factory=dict)


class PromptStrategy(Protocol):
    name: str

    def build(self, question: str, analysis_dict: dict, frame: pd.DataFrame) -> PromptPayload: ...


@dataclass
class GroundedStrategy:
    """Sends only precomputed KPIs and anomalies. Never raw issue rows."""

    name: str = GROUNDED

    def build(
        self, question: str, analysis_dict: dict, frame: pd.DataFrame
    ) -> PromptPayload:
        payload = json.dumps(analysis_dict, indent=2, sort_keys=True, default=str)

        user = (
            f"{question.strip()}\n\n"
            "Project data (this is the complete set of facts available to you):\n"
            f"```json\n{payload}\n```"
        )

        return PromptPayload(
            system=GROUNDED_SYSTEM,
            user=user,
            strategy=self.name,
            grounding_payload=analysis_dict,
            metadata={"payload_bytes": len(payload)},
        )


@dataclass
class NaiveStrategy:
    """The FR-D5 baseline: raw issue rows straight into the prompt.

    This is what the project argues against, implemented faithfully so the
    argument can be measured rather than asserted.
    """

    name: str = NAIVE
    max_rows: int = NAIVE_MAX_ROWS

    def build(
        self, question: str, analysis_dict: dict, frame: pd.DataFrame
    ) -> PromptPayload:
        columns = [c for c in NAIVE_COLUMNS if c in frame.columns]
        rows = frame[columns]

        truncated = len(rows) > self.max_rows
        if truncated:
            rows = rows.head(self.max_rows)

        table = rows.to_csv(index=False)

        note = (
            f"\n\nNote: only the first {self.max_rows} of {len(frame)} issues are "
            "shown."
            if truncated
            else ""
        )
        user = (
            f"{question.strip()}\n\n"
            f"Issue export ({len(rows)} rows):\n"
            f"```csv\n{table}```{note}"
        )

        return PromptPayload(
            system=NAIVE_SYSTEM,
            user=user,
            strategy=self.name,
            grounding_payload=None,
            metadata={
                "rows_sent": int(len(rows)),
                "rows_total": int(len(frame)),
                "truncated": truncated,
            },
        )


def get_strategy(name: str) -> PromptStrategy:
    strategies = {GROUNDED: GroundedStrategy(), NAIVE: NaiveStrategy()}
    if name not in strategies:
        raise ValueError(
            f"Unknown prompting strategy '{name}'. Expected one of: "
            + ", ".join(sorted(strategies))
        )
    return strategies[name]
