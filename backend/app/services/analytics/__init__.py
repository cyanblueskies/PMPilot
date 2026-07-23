"""Analytics: the deterministic track.

No FastAPI and no LLM imports. Every function takes data and returns values
(.claude/rules/architecture.md).
"""

from app.services.analytics.burndown import (
    BurndownPoint,
    BurndownReport,
    SprintBurndown,
    compute_burndown,
)
from app.services.analytics.frame import COLUMNS, ensure_frame, load_project_frame
from app.services.analytics.pipeline import (
    ProjectAnalysis,
    analyse,
    persist_analysis,
    run_analysis,
)
from app.services.analytics.kpi import (
    DefectReport,
    DurationReport,
    SprintVelocity,
    VelocityReport,
    compute_cycle_time,
    compute_defect_density,
    compute_lead_time,
    compute_velocity,
    is_blocked,
    is_defect,
    is_done,
)

__all__ = [
    "COLUMNS",
    "ensure_frame",
    "load_project_frame",
    "compute_velocity",
    "compute_defect_density",
    "compute_cycle_time",
    "compute_lead_time",
    "compute_burndown",
    "analyse",
    "run_analysis",
    "persist_analysis",
    "ProjectAnalysis",
    "BurndownReport",
    "SprintBurndown",
    "BurndownPoint",
    "VelocityReport",
    "SprintVelocity",
    "DefectReport",
    "DurationReport",
    "is_done",
    "is_blocked",
    "is_defect",
]
