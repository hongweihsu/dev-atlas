from fastapi.testclient import TestClient

from devatlas.main import app


def test_health_returns_typed_service_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "devatlas-api"}
