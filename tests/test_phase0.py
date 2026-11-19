from fastapi.testclient import TestClient

from dockship.config import settings
from dockship.main import app

client = TestClient(app)


def test_health_is_public():
    assert client.get("/health").status_code == 200


def test_apps_requires_key():
    assert client.get("/apps").status_code == 401


def test_apps_accepts_key():
    response = client.get("/apps", headers={"X-API-Key": settings.dockship_api_key})
    assert response.status_code == 200
    assert response.json() == []
