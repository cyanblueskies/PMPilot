"""Health endpoint.

Runs offline: the endpoint reports database reachability rather than requiring
it, so these pass with no container running.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    # Arrange / Act
    response = client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_database_state():
    response = client.get("/api/health")

    database = response.json()["database"]
    assert database == "up" or database.startswith("down:")


def test_health_stays_ok_when_database_is_unreachable():
    """A degraded dependency must not make the service report itself down.

    The dashboard is required to keep working without the LLM, and the same
    principle applies here: health is about this process, with dependency state
    reported alongside rather than folded into the status.
    """
    response = client.get("/api/health")

    assert response.status_code == 200
