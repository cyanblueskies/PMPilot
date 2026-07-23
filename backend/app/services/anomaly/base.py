"""Detector interface and result type.

Detection is a strategy, not logic inlined into a route handler: FR-C5 may add
an Isolation Forest detector later, and that must be a new implementation
rather than an edit to existing code (.claude/rules/architecture.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol

import pandas as pd

# Shared vocabulary with the FR-A4 ground-truth manifest, so detection F1 is a
# direct comparison rather than a mapping exercise.
VELOCITY_DROP = "velocity_drop"
OVERDUE_PILEUP = "overdue_pileup"
BLOCKED_CLUSTER = "blocked_cluster"

# Below this many sprints, "unusual compared to the others" has no meaning.
MIN_SPRINTS_FOR_COMPARISON = 4


@dataclass
class DetectedAnomaly:
    sprint: str
    sprint_sequence: int
    anomaly_type: str
    # 0-1. How far past the threshold, not how bad the situation is — a
    # consumer ranking by this is ranking by statistical unusualness.
    severity: float
    # The evidence: the numbers that triggered it, the threshold applied, and
    # the issues involved. This is what the grounded prompt cites, so it has to
    # stand alone without the frame it came from.
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class Detector(Protocol):
    anomaly_type: str

    def detect(self, frame: pd.DataFrame) -> list[DetectedAnomaly]: ...


def clamp_severity(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)
