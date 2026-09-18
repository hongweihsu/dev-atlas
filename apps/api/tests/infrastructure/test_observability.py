import json
import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from retrieval_works.api.routes.metrics import router as metrics_router
from retrieval_works.core.config import Settings
from retrieval_works.infrastructure.observability import (
    HttpMetrics,
    RequestObservabilityMiddleware,
)


def _application(*, token: str | None = "metrics-secret") -> FastAPI:
    application = FastAPI()
    http_metrics = HttpMetrics.create()
    application.state.http_metrics = http_metrics
    application.state.settings = Settings(
        observability_metrics_token=SecretStr(token) if token else None
    )
    application.add_middleware(
        RequestObservabilityMiddleware,
        metrics=http_metrics,
    )

    @application.get("/documents/{document_id}")
    async def get_document(document_id: str) -> dict[str, str]:
        return {"document_id": document_id}

    application.include_router(metrics_router)
    return application


def test_middleware_preserves_safe_request_id_and_logs_only_route_template(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = _application()

    with caplog.at_level(logging.INFO, logger="retrieval_works.requests"):
        response = TestClient(application).get(
            "/documents/private-document?query=private-question",
            headers={"X-Request-ID": "request-1234"},
        )

    assert response.headers["x-request-id"] == "request-1234"
    record = json.loads(caplog.records[-1].message)
    assert record["route"] == "/documents/{document_id}"
    assert record["status_code"] == 200
    assert "private-document" not in caplog.text
    assert "private-question" not in caplog.text


def test_middleware_replaces_unsafe_request_id() -> None:
    response = TestClient(_application()).get(
        "/documents/example",
        headers={"X-Request-ID": "contains spaces and private text"},
    )

    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32
    assert request_id.isalnum()


def test_metrics_endpoint_requires_token_and_exports_bounded_labels() -> None:
    application = _application()
    application.state.http_metrics.record_workflow(
        workflow="corrective_answer", outcome="provider_unavailable"
    )
    client = TestClient(application)
    client.get("/documents/private-document")

    unauthorized = client.get("/metrics")
    response = client.get(
        "/metrics", headers={"Authorization": "Bearer metrics-secret"}
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert 'route="/documents/{document_id}"' in response.text
    assert 'status_code="200"' in response.text
    assert (
        'retrieval_works_workflow_operations_total{outcome="provider_unavailable",'
        'workflow="corrective_answer"} 1.0'
    ) in response.text
    assert "private-document" not in response.text


def test_workflow_log_uses_request_correlation_without_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = _application()

    @application.get("/workflow")
    async def workflow() -> dict[str, str]:
        application.state.http_metrics.record_workflow(
            workflow="search", outcome="no_results"
        )
        return {"answer": "private answer"}

    with caplog.at_level(logging.INFO, logger="retrieval_works.workflows"):
        TestClient(application).get(
            "/workflow?question=private-question",
            headers={"X-Request-ID": "workflow-1234"},
        )

    workflow_record = next(
        json.loads(record.message)
        for record in caplog.records
        if '"event":"workflow_completed"' in record.message
    )
    assert workflow_record == {
        "event": "workflow_completed",
        "outcome": "no_results",
        "request_id": "workflow-1234",
        "workflow": "search",
    }
    assert "private-question" not in caplog.text
    assert "private answer" not in caplog.text


def test_metrics_endpoint_is_unavailable_when_not_configured() -> None:
    response = TestClient(_application(token=None)).get("/metrics")

    assert response.status_code == 503


def test_metrics_capture_failure_then_recovery() -> None:
    application = _application()
    attempts = 0

    @application.get("/transient-provider")
    async def transient_provider() -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPException(status_code=503, detail="provider unavailable")
        return {"status": "recovered"}

    client = TestClient(application)
    failed = client.get("/transient-provider")
    recovered = client.get("/transient-provider")
    metrics = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})

    assert failed.status_code == 503
    assert recovered.status_code == 200
    assert (
        'retrieval_works_http_requests_total{method="GET",route="/transient-provider",'
        'status_code="503"} 1.0'
    ) in metrics.text
    assert (
        'retrieval_works_http_requests_total{method="GET",route="/transient-provider",'
        'status_code="200"} 1.0'
    ) in metrics.text
