"""Shared fixtures.

Realistic data comes from the FR-A4 generator with a fixed seed rather than
hand-written CSV, so fixtures and evaluation data are the same shape
(.claude/rules/testing.md).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "data" / "scripts" / "generate_dataset.py"

# Tables emptied between database tests, children first.
TABLES = ("anomalies", "kpi_snapshots", "reports", "query_logs", "issues", "sprints", "projects")


def _database_reachable() -> bool:
    from app.db.session import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def database_required() -> None:
    """Skip when no database is running — unless CI says there must be one.

    Locally, `pytest` should work without starting Docker. In CI a Postgres
    service is always present, so a skip there would mean these tests quietly
    stopped running. PMPILOT_REQUIRE_DB=1 turns that skip into a failure.
    """
    if _database_reachable():
        return
    message = "database not reachable at DATABASE_URL"
    if os.getenv("PMPILOT_REQUIRE_DB") == "1":
        pytest.fail(f"PMPILOT_REQUIRE_DB=1 but {message}")
    pytest.skip(message)


@pytest.fixture
def clean_db(database_required) -> None:
    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def generated_dataset(tmp_path_factory) -> Path:
    """A small, fixed-seed dataset. Returns the output directory."""
    out = tmp_path_factory.mktemp("generated")
    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--seed", "42",
            "--sprints", "6",
            "--issues-per-sprint", "20",
            "--name", "fixture",
            "--out", str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="session")
def generated_csv_bytes(generated_dataset: Path) -> bytes:
    return (generated_dataset / "fixture.csv").read_bytes()


@pytest.fixture(scope="session")
def generated_manifest(generated_dataset: Path) -> dict:
    import json

    return json.loads((generated_dataset / "fixture.truth.json").read_text())
