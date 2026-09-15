from __future__ import annotations

import json
import logging
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_UNMATCHED_ROUTE = "unmatched"
_request_id_context: ContextVar[str | None] = ContextVar(
    "devatlas_request_id", default=None
)


@dataclass(frozen=True, slots=True)
class HttpMetrics:
    registry: CollectorRegistry
    requests: Counter
    duration: Histogram
    workflows: Counter

    @classmethod
    def create(cls) -> HttpMetrics:
        registry = CollectorRegistry()
        return cls(
            registry=registry,
            requests=Counter(
                "requests_total",
                "Total HTTP requests handled.",
                labelnames=("method", "route", "status_code"),
                namespace="devatlas",
                subsystem="http",
                registry=registry,
            ),
            duration=Histogram(
                "request_duration_seconds",
                "HTTP request duration in seconds.",
                labelnames=("method", "route"),
                namespace="devatlas",
                subsystem="http",
                registry=registry,
            ),
            workflows=Counter(
                "operations_total",
                "Total bounded AI and retrieval workflow outcomes.",
                labelnames=("workflow", "outcome"),
                namespace="devatlas",
                subsystem="workflow",
                registry=registry,
            ),
        )

    def observe(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        self.requests.labels(
            method=method,
            route=route,
            status_code=str(status_code),
        ).inc()
        self.duration.labels(method=method, route=route).observe(duration_seconds)

    def record_workflow(self, *, workflow: str, outcome: str) -> None:
        self.workflows.labels(workflow=workflow, outcome=outcome).inc()
        logging.getLogger("devatlas.workflows").info(
            json.dumps(
                {
                    "event": "workflow_completed",
                    "request_id": _request_id_context.get(),
                    "workflow": workflow,
                    "outcome": outcome,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )


class RequestObservabilityMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        metrics: HttpMetrics,
        logger: logging.Logger | None = None,
    ) -> None:
        self._app = app
        self._metrics = metrics
        self._logger = logger or logging.getLogger("devatlas.requests")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _request_id(headers.get("x-request-id"))
        context_token = _request_id_context.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["x-request-id"] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            duration_seconds = time.perf_counter() - started_at
            route = _route_template(scope)
            method = str(scope.get("method", "UNKNOWN"))
            self._metrics.observe(
                method=method,
                route=route,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
            self._logger.info(
                json.dumps(
                    {
                        "event": "http_request_completed",
                        "request_id": request_id,
                        "method": method,
                        "route": route,
                        "status_code": status_code,
                        "duration_ms": round(duration_seconds * 1000, 3),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            _request_id_context.reset(context_token)


def _request_id(candidate: str | None) -> str:
    if candidate is not None and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


def _route_template(scope: Scope) -> str:
    route: Any = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else _UNMATCHED_ROUTE
