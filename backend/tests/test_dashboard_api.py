"""FR-E1 / FR-E2 / FR-E3 — dashboard and anomaly endpoints.

Also covers the pipeline that populates kpi_snapshots and anomalies. Those are
Must-tier evaluation instrumentation, so "the table has rows after an upload" is
a behaviour worth asserting, not an implementation detail.
"""

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import app
from app.models.analytics import Anomaly, KpiSnapshot
from app.models.project import Project

client = TestClient(app)


@pytest.fixture
def project_id(clean_db, generated_csv_bytes) -> int:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("demo.csv", io.BytesIO(generated_csv_bytes), "text/csv")},
    )
    assert response.status_code == 202
    return response.json()["project_id"]


# --- the pipeline runs on upload -------------------------------------------


def test_upload_populates_kpi_snapshots(project_id):
    with SessionLocal() as session:
        count = session.scalar(
            select(func.count()).select_from(KpiSnapshot).where(
                KpiSnapshot.project_id == project_id
            )
        )

    assert count > 0


def test_upload_populates_anomalies(project_id):
    with SessionLocal() as session:
        count = session.scalar(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.project_id == project_id
            )
        )

    assert count > 0


def test_reanalysis_replaces_rather_than_appends(project_id, generated_csv_bytes):
    """A stale snapshot from an earlier run would be read as current."""
    from app.services.analytics import run_analysis

    with SessionLocal() as session:
        before = session.scalar(
            select(func.count()).select_from(KpiSnapshot).where(
                KpiSnapshot.project_id == project_id
            )
        )
        run_analysis(session, project_id)
        session.commit()
        after = session.scalar(
            select(func.count()).select_from(KpiSnapshot).where(
                KpiSnapshot.project_id == project_id
            )
        )

    assert after == before


def test_anomaly_rows_store_type_and_sprint_as_structured_columns(project_id):
    """The FR-A4 ground-truth comparison joins on these, not on prose."""
    with SessionLocal() as session:
        anomalies = session.scalars(
            select(Anomaly).where(Anomaly.project_id == project_id)
        ).all()

    assert anomalies
    for anomaly in anomalies:
        assert anomaly.anomaly_type
        assert anomaly.sprint_id is not None
        assert anomaly.detail


# --- dashboard -------------------------------------------------------------


def test_dashboard_returns_every_kpi_block(project_id):
    body = client.get(f"/api/projects/{project_id}/dashboard").json()

    assert set(body) == {
        "project",
        "velocity",
        "cycle_time",
        "lead_time",
        "defects",
        "burndown",
        "anomalies",
    }
    assert body["project"]["issue_count"] > 0


def test_dashboard_series_can_be_omitted(project_id):
    with_series = client.get(f"/api/projects/{project_id}/dashboard").json()
    without = client.get(
        f"/api/projects/{project_id}/dashboard?include_series=false"
    ).json()

    assert with_series["burndown"]["sprints"][0]["points"]
    assert "points" not in without["burndown"]["sprints"][0]
    assert len(str(without)) < len(str(with_series))


def test_dashboard_matches_the_stored_anomaly_count(project_id):
    body = client.get(f"/api/projects/{project_id}/dashboard").json()
    stored = client.get(f"/api/projects/{project_id}/anomalies").json()

    assert len(body["anomalies"]) == len(stored)


def test_dashboard_is_404_for_an_unknown_project(clean_db):
    assert client.get("/api/projects/999999/dashboard").status_code == 404


def test_dashboard_is_409_while_a_project_is_still_processing(clean_db):
    """Exists but not analysable yet is a different answer from not existing."""
    with SessionLocal() as session:
        project = Project(name="pending", ingest_status="processing")
        session.add(project)
        session.commit()
        pending_id = project.id

    response = client.get(f"/api/projects/{pending_id}/dashboard")

    assert response.status_code == 409
    assert "processing" in response.json()["detail"]


# --- anomalies -------------------------------------------------------------


def test_anomalies_endpoint_returns_evidence_with_each_finding(project_id):
    findings = client.get(f"/api/projects/{project_id}/anomalies").json()

    assert findings
    for finding in findings:
        assert finding["anomaly_type"]
        assert finding["sprint"]
        assert finding["detail"]


def test_anomalies_are_ordered_most_severe_first(project_id):
    severities = [
        f["severity"] for f in client.get(f"/api/projects/{project_id}/anomalies").json()
    ]

    assert severities == sorted(severities, reverse=True)


def test_anomalies_can_be_filtered_by_type(project_id):
    all_findings = client.get(f"/api/projects/{project_id}/anomalies").json()
    wanted = all_findings[0]["anomaly_type"]

    filtered = client.get(
        f"/api/projects/{project_id}/anomalies?anomaly_type={wanted}"
    ).json()

    assert filtered
    assert {f["anomaly_type"] for f in filtered} == {wanted}


def test_dashboard_and_anomalies_work_without_any_llm(project_id, monkeypatch):
    """Graceful degradation: these views are required to work with the
    generative track entirely unavailable (.claude/rules/architecture.md).
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    assert client.get(f"/api/projects/{project_id}/dashboard").status_code == 200
    assert client.get(f"/api/projects/{project_id}/anomalies").status_code == 200
