"""FR-A1 — upload endpoint and ingestion status.

Requires a database. TestClient runs BackgroundTasks synchronously once the
response is produced, so persistence has completed by the time each request
returns here.
"""

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import app
from app.models.project import Issue, Project, Sprint

client = TestClient(app)

MINIMAL = b"Issue Key,Status,Sprint\nPM-1,Done,Sprint 1\nPM-2,Blocked,Sprint 1\n"


def upload(content: bytes, filename: str = "export.csv"):
    return client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


def test_upload_accepts_a_valid_file(clean_db):
    response = upload(MINIMAL)

    assert response.status_code == 202
    body = response.json()
    assert body["row_count"] == 2
    assert body["status"] == "processing"


def test_upload_persists_issues_and_marks_project_ready(clean_db):
    project_id = upload(MINIMAL).json()["project_id"]

    status = client.get(f"/api/projects/{project_id}").json()

    assert status["status"] == "ready"
    assert status["issue_count"] == 2
    assert status["error"] is None


def test_upload_creates_sprints_and_links_issues(clean_db):
    content = (
        b"Issue Key,Status,Sprint,Created Date\n"
        b"PM-1,Done,Sprint 1,2026-01-05T09:00:00+00:00\n"
        b"PM-2,Done,Sprint 2,2026-01-19T09:00:00+00:00\n"
    )
    project_id = upload(content).json()["project_id"]

    with SessionLocal() as session:
        sprints = session.scalars(
            select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.sequence)
        ).all()
        linked = session.scalar(
            select(func.count())
            .select_from(Issue)
            .where(Issue.project_id == project_id, Issue.sprint_id.is_not(None))
        )

    assert [s.name for s in sprints] == ["Sprint 1", "Sprint 2"]
    assert linked == 2


def test_sprints_are_ordered_chronologically_not_alphabetically(clean_db):
    """"Sprint 10" sorts before "Sprint 2" as text. Order must come from dates."""
    content = (
        b"Issue Key,Status,Sprint,Created Date\n"
        b"PM-1,Done,Sprint 10,2026-06-01T09:00:00+00:00\n"
        b"PM-2,Done,Sprint 2,2026-01-05T09:00:00+00:00\n"
    )
    project_id = upload(content).json()["project_id"]

    with SessionLocal() as session:
        names = [
            s.name
            for s in session.scalars(
                select(Sprint)
                .where(Sprint.project_id == project_id)
                .order_by(Sprint.sequence)
            ).all()
        ]

    assert names == ["Sprint 2", "Sprint 10"]


def test_blank_story_points_persist_as_null_not_zero(clean_db):
    content = (
        b"Issue Key,Status,Sprint,Story Points\n"
        b"PM-1,Done,Sprint 1,5\n"
        b"PM-2,Done,Sprint 1,\n"
    )
    project_id = upload(content).json()["project_id"]

    with SessionLocal() as session:
        points = {
            i.issue_key: i.story_points
            for i in session.scalars(
                select(Issue).where(Issue.project_id == project_id)
            ).all()
        }

    assert points["PM-1"] == 5
    assert points["PM-2"] is None


def test_missing_required_column_returns_422_naming_the_column(clean_db):
    response = upload(b"Issue Key,Status\nPM-1,Done\n")

    assert response.status_code == 422
    assert "sprint" in response.json()["detail"].lower()


def test_unsupported_extension_returns_400(clean_db):
    response = upload(MINIMAL, filename="export.txt")

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_rejected_upload_creates_no_project(clean_db):
    upload(b"Issue Key,Status\nPM-1,Done\n")

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Project)) == 0


def test_unknown_project_returns_404(clean_db):
    assert client.get("/api/projects/999999").status_code == 404


def test_upload_reports_degraded_kpis_for_missing_optional_fields(clean_db):
    body = upload(MINIMAL).json()

    assert "story_points" in body["missing_optional_fields"]
    assert any("velocity" in k for k in body["degraded_kpis"])


def test_generated_dataset_uploads_end_to_end(clean_db, generated_csv_bytes):
    response = upload(generated_csv_bytes, filename="fixture.csv")

    assert response.status_code == 202
    body = response.json()
    assert body["missing_optional_fields"] == []

    status = client.get(f"/api/projects/{body['project_id']}").json()
    assert status["status"] == "ready"
    assert status["issue_count"] == body["row_count"]
