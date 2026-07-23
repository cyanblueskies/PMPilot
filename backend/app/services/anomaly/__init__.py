"""Anomaly detection: the deterministic track's second half.

No FastAPI and no LLM imports (.claude/rules/architecture.md).
"""

from __future__ import annotations

import pandas as pd

from app.services.anomaly.base import (
    BLOCKED_CLUSTER,
    MIN_SPRINTS_FOR_COMPARISON,
    OVERDUE_PILEUP,
    VELOCITY_DROP,
    DetectedAnomaly,
    Detector,
)
from app.services.anomaly.detectors import (
    BlockedClusterDetector,
    OverduePileupDetector,
    VelocityDropDetector,
)
from app.services.anomaly.scoring import DetectionScore, TypeScore, score_detections


def default_detectors() -> list[Detector]:
    """The detectors FR-C1 to FR-C3 require.

    A new detector (FR-C5's Isolation Forest, say) joins this list rather than
    editing any existing one.
    """
    return [
        VelocityDropDetector(),
        OverduePileupDetector(),
        BlockedClusterDetector(),
    ]


def detect_all(
    frame: pd.DataFrame, detectors: list[Detector] | None = None
) -> list[DetectedAnomaly]:
    """Run every detector and return findings in sprint order, worst first."""
    found: list[DetectedAnomaly] = []
    for detector in detectors if detectors is not None else default_detectors():
        found.extend(detector.detect(frame))

    return sorted(found, key=lambda a: (a.sprint_sequence, -a.severity))


__all__ = [
    "detect_all",
    "default_detectors",
    "DetectedAnomaly",
    "Detector",
    "VelocityDropDetector",
    "OverduePileupDetector",
    "BlockedClusterDetector",
    "score_detections",
    "DetectionScore",
    "TypeScore",
    "VELOCITY_DROP",
    "OVERDUE_PILEUP",
    "BLOCKED_CLUSTER",
    "MIN_SPRINTS_FOR_COMPARISON",
]
