from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ISSUE_TYPES = ["Story", "Bug", "Task", "Sub-task"]
ISSUE_TYPE_WEIGHTS = [0.45, 0.25, 0.25, 0.05]
PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest"]
PRIORITY_WEIGHTS = [0.05, 0.20, 0.50, 0.20, 0.05]
STORY_POINTS = [1, 2, 3, 5, 8, 13]
STORY_POINT_WEIGHTS = [0.15, 0.25, 0.25, 0.20, 0.10, 0.05]
LABEL_POOL = ["frontend", "backend", "api", "infra", "ux", "tech-debt", "urgent"]
EPIC_POOL = ["EPIC-1", "EPIC-2", "EPIC-3", "EPIC-4"]

ANOMALY_TYPES = ["velocity_drop", "overdue_pileup", "blocked_cluster"]

# Sprints 0 and 1 stay clean so the detectors have a baseline to measure against.
# Injecting into sprint 0 would make a velocity drop undetectable by construction.
MIN_CLEAN_SPRINTS = 2


@dataclass
class Config:
    seed: int = 42
    sprints: int = 12
    sprint_days: int = 14
    team_size: int = 6
    issues_per_sprint: int = 40
    # Kept tight on purpose. Real teams are reasonably stable sprint to sprint, and
    # more importantly: natural velocity noise is the floor an injected drop has to
    # clear. At sd=6 the baseline swung 82-192 points and a genuine 46% drop only
    # reached z=-1.5, i.e. invisible to a standard -2 threshold.
    issues_per_sprint_sd: float = 3.0
    completion_rate: float = 0.82
    blocked_rate: float = 0.05
    bug_rate: float = 0.25
    anomaly_rate: float = 0.25
    start_date: str = "2026-01-05"


@dataclass
class InjectedAnomaly:
    sprint: str
    sprint_index: int
    type: str
    params: dict = field(default_factory=dict)
    issue_keys: list[str] = field(default_factory=list)


def _iso(dt: datetime) -> str:
    """UTC-aware ISO 8601. Ingestion must parse to UTC — see code-style.md."""
    return dt.astimezone(timezone.utc).isoformat()


def _pick(rng: np.random.Generator, values: list, weights: list):
    return values[rng.choice(len(values), p=weights)]


def plan_anomalies(rng: np.random.Generator, cfg: Config) -> list[InjectedAnomaly]:
    """Decide which sprints carry which anomaly, before any issue is generated."""
    eligible = list(range(MIN_CLEAN_SPRINTS, cfg.sprints))
    n = min(int(round(cfg.sprints * cfg.anomaly_rate)), len(eligible))
    if n == 0:
        return []

    chosen = sorted(rng.choice(eligible, size=n, replace=False).tolist())

    # Assign types round-robin, not independently at random. Independent draws
    # routinely produce a run with zero instances of some type — and a detector
    # whose target anomaly never appears cannot be scored at all.
    order = ANOMALY_TYPES.copy()
    rng.shuffle(order)
    return [
        InjectedAnomaly(
            sprint=f"Sprint {i + 1}",
            sprint_index=i,
            type=order[idx % len(order)],
        )
        for idx, i in enumerate(chosen)
    ]


def generate(cfg: Config) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(cfg.seed)

    team = [f"user{i + 1}" for i in range(cfg.team_size)]
    start = datetime.fromisoformat(cfg.start_date).replace(tzinfo=timezone.utc)

    anomalies = plan_anomalies(rng, cfg)
    by_sprint = {a.sprint_index: a for a in anomalies}

    rows: list[dict] = []
    counter = 1
    sprint_end_by_name: dict[str, str] = {}

    for s in range(cfg.sprints):
        sprint_name = f"Sprint {s + 1}"
        sprint_start = start + timedelta(days=s * cfg.sprint_days)
        sprint_end = sprint_start + timedelta(days=cfg.sprint_days)
        sprint_end_by_name[sprint_name] = _iso(sprint_end)
        anomaly = by_sprint.get(s)

        n_issues = max(
            5, int(round(rng.normal(cfg.issues_per_sprint, cfg.issues_per_sprint_sd)))
        )

        # Anomaly parameters shift this sprint's generation away from baseline.
        completion_rate = cfg.completion_rate
        blocked_rate = cfg.blocked_rate
        overdue_rate = 0.05
        blocked_victim = None

        if anomaly is not None:
            if anomaly.type == "velocity_drop":
                completion_rate = cfg.completion_rate * float(rng.uniform(0.22, 0.38))
                anomaly.params = {
                    "baseline_completion_rate": round(cfg.completion_rate, 3),
                    "injected_completion_rate": round(completion_rate, 3),
                }
            elif anomaly.type == "overdue_pileup":
                # More work in, same work out. Issue count rises and completion rate
                # falls by the same factor, so the *absolute* number of completed
                # points stays near baseline — velocity looks healthy while unclosed
                # past-due work piles up.
                #
                # Holding velocity steady is the whole point: depressing it would also
                # trip FR-C1, and the two anomaly types would be indistinguishable in
                # the ground truth, making per-detector F1 meaningless.
                scope_factor = float(rng.uniform(1.5, 1.9))
                n_issues = int(round(n_issues * scope_factor))
                completion_rate = cfg.completion_rate / scope_factor
                overdue_rate = float(rng.uniform(0.60, 0.80))
                anomaly.params = {
                    "scope_factor": round(scope_factor, 3),
                    "baseline_completion_rate": round(cfg.completion_rate, 3),
                    "injected_completion_rate": round(completion_rate, 3),
                    "injected_overdue_rate": round(overdue_rate, 3),
                }
            elif anomaly.type == "blocked_cluster":
                blocked_rate = float(rng.uniform(0.30, 0.45))
                blocked_victim = team[int(rng.integers(len(team)))]
                anomaly.params = {
                    "baseline_blocked_rate": round(cfg.blocked_rate, 3),
                    "injected_blocked_rate": round(blocked_rate, 3),
                    "concentrated_on": blocked_victim,
                }

        for _ in range(n_issues):
            key = f"PM-{counter}"
            counter += 1

            # A blocked cluster concentrates on one person; normal work spreads out.
            if blocked_victim is not None and rng.random() < 0.7:
                assignee = blocked_victim
            else:
                assignee = team[int(rng.integers(len(team)))]

            is_bug = rng.random() < cfg.bug_rate
            issue_type = "Bug" if is_bug else _pick(rng, ISSUE_TYPES, ISSUE_TYPE_WEIGHTS)
            points = _pick(rng, STORY_POINTS, STORY_POINT_WEIGHTS)

            created = sprint_start + timedelta(
                hours=float(rng.uniform(0, cfg.sprint_days * 24 * 0.6))
            )
            due = sprint_start + timedelta(
                days=float(rng.uniform(cfg.sprint_days * 0.4, cfg.sprint_days))
            )

            is_overdue = False
            roll = rng.random()
            if roll < blocked_rate:
                status, resolved = "Blocked", None
            elif roll < blocked_rate + completion_rate:
                status = "Done"
                # Resolve somewhere between creation and a little past sprint end,
                # so cycle time has a realistic spread rather than a constant.
                span = (sprint_end - created).total_seconds()
                resolved = created + timedelta(
                    seconds=float(rng.uniform(span * 0.15, span * 1.10))
                )
            else:
                status = "To Do" if rng.random() < 0.4 else "In Progress"
                resolved = None
                # Applied to every unresolved issue, not gated behind the completion
                # branch — that gating was why the nominal rate never materialised.
                if rng.random() < overdue_rate:
                    due = sprint_start + timedelta(days=float(rng.uniform(1, 4)))
                    is_overdue = True

            if anomaly is not None and (
                (anomaly.type == "blocked_cluster" and status == "Blocked")
                or (anomaly.type == "overdue_pileup" and is_overdue)
            ):
                anomaly.issue_keys.append(key)

            n_labels = int(rng.integers(0, 3))
            labels = rng.choice(LABEL_POOL, size=n_labels, replace=False).tolist()
            estimate = points * 4 * 3600
            spent = int(estimate * float(rng.uniform(0.6, 1.8))) if resolved else 0

            rows.append(
                {
                    "Issue Key": key,
                    "Issue Type": issue_type,
                    "Status": status,
                    "Assignee": assignee,
                    "Reporter": team[int(rng.integers(len(team)))],
                    "Priority": _pick(rng, PRIORITIES, PRIORITY_WEIGHTS),
                    "Story Points": points,
                    "Sprint": sprint_name,
                    "Created Date": _iso(created),
                    "Resolved Date": _iso(resolved) if resolved else "",
                    "Due Date": _iso(due),
                    "Labels": ",".join(labels),
                    "Epic Link": EPIC_POOL[int(rng.integers(len(EPIC_POOL)))],
                    "Original Estimate": estimate,
                    "Time Spent": spent,
                    "Description": f"Synthetic issue {key} in {sprint_name}.",
                    "Comments": "",
                }
            )

    df = pd.DataFrame(rows)

    # Per-sprint counts go in the manifest so the ground truth is self-verifying:
    # an injected anomaly that doesn't separate from the baseline here is a broken
    # label, and F1 measured against it would be meaningless.
    done = df[df["Status"] == "Done"]
    velocity = done.groupby("Sprint")["Story Points"].sum().to_dict()
    blocked = df[df["Status"] == "Blocked"].groupby("Sprint").size().to_dict()
    unresolved = df[df["Status"] != "Done"]
    overdue = (
        unresolved[
            pd.to_datetime(unresolved["Due Date"], utc=True)
            < pd.to_datetime(unresolved["Sprint"].map(sprint_end_by_name), utc=True)
        ]
        .groupby("Sprint")
        .size()
        .to_dict()
    )
    per_sprint = {
        f"Sprint {i + 1}": {
            "velocity": int(velocity.get(f"Sprint {i + 1}", 0)),
            "blocked": int(blocked.get(f"Sprint {i + 1}", 0)),
            "overdue_at_sprint_end": int(overdue.get(f"Sprint {i + 1}", 0)),
        }
        for i in range(cfg.sprints)
    }

    manifest = {
        "generator": "FR-A4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": asdict(cfg),
        "totals": {
            "issues": len(df),
            "sprints": cfg.sprints,
            "done": int((df["Status"] == "Done").sum()),
            "blocked": int((df["Status"] == "Blocked").sum()),
        },
        "per_sprint": per_sprint,
        "anomalies": [asdict(a) for a in anomalies],
    }
    return df, manifest


def main() -> None:
    cfg_defaults = Config()
    p = argparse.ArgumentParser(description="FR-A4 synthetic Jira dataset generator")
    p.add_argument("--seed", type=int, default=cfg_defaults.seed)
    p.add_argument("--sprints", type=int, default=cfg_defaults.sprints)
    p.add_argument("--team-size", type=int, default=cfg_defaults.team_size)
    p.add_argument("--issues-per-sprint", type=int, default=cfg_defaults.issues_per_sprint)
    p.add_argument("--anomaly-rate", type=float, default=cfg_defaults.anomaly_rate)
    p.add_argument("--name", default="demo")
    p.add_argument("--out", default="data/sample")
    args = p.parse_args()

    cfg = Config(
        seed=args.seed,
        sprints=args.sprints,
        team_size=args.team_size,
        issues_per_sprint=args.issues_per_sprint,
        anomaly_rate=args.anomaly_rate,
    )

    df, manifest = generate(cfg)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{args.name}.csv"
    truth_path = out / f"{args.name}.truth.json"

    df.to_csv(csv_path, index=False, encoding="utf-8")
    truth_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{csv_path}  ({len(df)} issues, {cfg.sprints} sprints)")
    print(f"{truth_path}  ({len(manifest['anomalies'])} injected anomalies)")
    for a in manifest["anomalies"]:
        print(f"  {a['sprint']:<10} {a['type']}")


if __name__ == "__main__":
    main()
