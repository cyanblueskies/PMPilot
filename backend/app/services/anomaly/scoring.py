"""Detection scoring against the FR-A4 ground-truth manifest.

This is Must-tier evaluation instrumentation, not a test helper: the F1 figures
it produces go into the dissertation's evaluation chapter, and it ships with
the detectors rather than after them (.claude/rules/scope.md).

A prediction counts as correct only when both the sprint and the anomaly type
match. Flagging the right sprint for the wrong reason is not a detection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.anomaly.base import DetectedAnomaly


@dataclass
class TypeScore:
    anomaly_type: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetectionScore:
    overall: TypeScore
    by_type: list[TypeScore] = field(default_factory=list)
    matched: list[dict] = field(default_factory=list)
    missed: list[dict] = field(default_factory=list)
    spurious: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall.to_dict(),
            "by_type": [t.to_dict() for t in self.by_type],
            "matched": self.matched,
            "missed": self.missed,
            "spurious": self.spurious,
        }


def _score(anomaly_type: str, tp: int, fp: int, fn: int) -> TypeScore:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall
        else (0.0 if precision is not None and recall is not None else None)
    )
    return TypeScore(
        anomaly_type=anomaly_type,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 3) if precision is not None else None,
        recall=round(recall, 3) if recall is not None else None,
        f1=round(f1, 3) if f1 is not None else None,
    )


def score_detections(
    detected: list[DetectedAnomaly], manifest: dict
) -> DetectionScore:
    """Compare detector output against the injected ground truth."""
    truth = {
        (a["sprint"], a["type"]) for a in manifest.get("anomalies", [])
    }
    predicted = {(d.sprint, d.anomaly_type) for d in detected}

    matched = sorted(truth & predicted)
    missed = sorted(truth - predicted)
    spurious = sorted(predicted - truth)

    types = sorted({t for _, t in truth} | {t for _, t in predicted})
    by_type = [
        _score(
            anomaly_type=t,
            tp=sum(1 for _, ty in matched if ty == t),
            fp=sum(1 for _, ty in spurious if ty == t),
            fn=sum(1 for _, ty in missed if ty == t),
        )
        for t in types
    ]

    return DetectionScore(
        overall=_score("overall", len(matched), len(spurious), len(missed)),
        by_type=by_type,
        matched=[{"sprint": s, "type": t} for s, t in matched],
        missed=[{"sprint": s, "type": t} for s, t in missed],
        spurious=[{"sprint": s, "type": t} for s, t in spurious],
    )
