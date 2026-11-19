from fastapi.testclient import TestClient

from dockship.config import settings
from dockship.main import app


def test_metrics_is_protected_and_exposes_deployment_metrics():
    client = TestClient(app)
    assert client.get("/metrics").status_code == 401
    response = client.get(
        "/metrics", headers={"X-API-Key": settings.dockship_api_key}
    )
    assert response.status_code == 200
    assert "dockship_deployments_total" in response.text
    assert "dockship_apps_active" in response.text
