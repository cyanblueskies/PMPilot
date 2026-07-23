"""The supported question set for FR-D1.

MVP scope is a limited, predefined set of question types over structured fields
— not open-ended natural language (.claude/rules/scope.md). The >80% accuracy
target is measured against *this* set, so it is defined in code rather than
left implicit, and the same list is used to route a question, to tell a user
what is supported, and to evaluate accuracy.

Anything outside it gets a friendly refusal rather than a guess. A wrong answer
delivered confidently is worse than a refusal, and the docs name this as the
mitigation for NL2SQL accuracy risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SupportedQuestion:
    key: str
    description: str
    # Words that suggest this intent. Deliberately simple: routing needs to be
    # inspectable and reproducible for the evaluation, and a classifier would
    # make accuracy figures depend on a second model.
    keywords: tuple[str, ...] = field(default_factory=tuple)
    example: str = ""


SUPPORTED_QUESTIONS: tuple[SupportedQuestion, ...] = (
    SupportedQuestion(
        key="blocked_by_assignee",
        description="Who has the most blocked issues, overall or in a sprint",
        keywords=(
            "blocked",
            "blocker",
            "blocking",
            "stuck",
            "impeded",
            "on hold",
            "waiting on",
        ),
        example="Who has the most blocked tasks this sprint?",
    ),
    SupportedQuestion(
        key="velocity_by_sprint",
        description="Story points completed per sprint",
        keywords=(
            "velocity",
            "story points",
            "points completed",
            "points did",
            "throughput",
            "delivered",
            "how much work",
            "output",
        ),
        example="What was our velocity in each sprint?",
    ),
    SupportedQuestion(
        key="overdue_issues",
        description="Issues past their due date and still open",
        keywords=(
            "overdue",
            "late",
            "past due",
            "due date",
            "missed deadline",
            "behind schedule",
            "slipping",
        ),
        example="Which issues are overdue?",
    ),
    SupportedQuestion(
        key="workload_by_assignee",
        description="How many issues or points each person is carrying",
        keywords=(
            "workload",
            "work load",
            "distributed",
            "distribution",
            "across the team",
            "spread",
            "who is working",
            "who has",
            "per person",
            "each person",
            "assigned",
            "assignee",
            "busiest",
            "capacity",
            "carrying",
        ),
        example="How is work distributed across the team?",
    ),
    SupportedQuestion(
        key="defects",
        description="Bug counts and the share of work that is defects",
        keywords=("bug", "defect", "quality", "fault", "regression"),
        example="How many bugs were raised in the last sprint?",
    ),
    SupportedQuestion(
        key="issue_status_breakdown",
        description="How many issues sit in each status",
        keywords=(
            "status",
            "how many issues",
            "how many tickets",
            "breakdown",
            "still open",
            "in progress",
            "to do",
            "not started",
            "remaining",
        ),
        example="How many issues are still open?",
    ),
    SupportedQuestion(
        key="cycle_time",
        description="How long issues take to complete",
        keywords=(
            "cycle time",
            "lead time",
            "how long",
            "duration",
            "takes to",
            "time to complete",
            "turnaround",
            "days to finish",
        ),
        example="How long does an issue take to finish?",
    ),
    SupportedQuestion(
        key="sprint_scope",
        description="How much work was added to a sprint after it started",
        keywords=(
            "scope",
            "scope creep",
            "added mid",
            "work added",
            "grew",
            "growth",
            "extra work",
        ),
        example="Did scope grow during sprint 3?",
    ),
    SupportedQuestion(
        key="anomalies",
        description="Which sprints were flagged as anomalous and why",
        keywords=(
            "anomaly",
            "anomalies",
            "anomalous",
            "unusual",
            "problem",
            "risk",
            "flagged",
            "went wrong",
            "concerning",
            "red flag",
        ),
        example="Which sprints look unusual?",
    ),
)


def classify(question: str) -> SupportedQuestion | None:
    """Route a question to a supported type, or None if it is out of scope.

    Scored by how many of a type's keywords appear, so a question mentioning
    several concepts lands on the one it matches most strongly.
    """
    text = (question or "").lower()
    if not text.strip():
        return None

    best: SupportedQuestion | None = None
    best_score = 0

    for supported in SUPPORTED_QUESTIONS:
        score = sum(1 for keyword in supported.keywords if keyword in text)
        if score > best_score:
            best, best_score = supported, score

    return best


def out_of_scope_message() -> str:
    lines = [
        "That question is outside what I can answer reliably from this data, "
        "so I would rather not guess.",
        "",
        "I can answer questions about:",
    ]
    lines += [f"  • {q.description} — e.g. \"{q.example}\"" for q in SUPPORTED_QUESTIONS]
    return "\n".join(lines)
