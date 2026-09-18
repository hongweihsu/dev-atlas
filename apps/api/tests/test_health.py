from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from devatlas.api.routes.health import router
from devatlas.infrastructure.readiness import ReadinessResult
from devatlas.main import app


def test_health_returns_typed_service_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "devatlas-api"}


@pytest.fixture
def readiness_api() -> Iterator[tuple[TestClient, AsyncMock]]:
    application = FastAPI()
    application.include_router(router)
    checker = AsyncMock()
    application.state.readiness_checker = checker
    with TestClient(application) as client:
        yield client, checker


def test_readiness_returns_dependency_status(
    readiness_api: tuple[TestClient, AsyncMock],
) -> None:
    client, checker = readiness_api
    checker.check.return_value = ReadinessResult(database=True, redis=True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
        "redis": "ok",
    }


def test_readiness_fails_when_a_dependency_is_unavailable(
    readiness_api: tuple[TestClient, AsyncMock],
) -> None:
    client, checker = readiness_api
    checker.check.return_value = ReadinessResult(database=True, redis=False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ok",
        "redis": "unavailable",
    }
