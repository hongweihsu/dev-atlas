# Observability and production hardening

DevAtlas uses a deliberately small observability stack for its low-traffic,
cost-capped demo. It exposes Prometheus-format application metrics, emits one
structured completion log per HTTP request, and uses AWS CloudWatch alarms for
continuous infrastructure and edge failure notification. It does not run an
always-on Prometheus or tracing cluster.

## Correlation and data boundary

Every HTTP response includes `X-Request-ID`. A caller-provided ID is retained
only when it contains 8–128 ASCII letters, digits, dots, underscores, or
hyphens; otherwise the API generates a random ID. Operators can use this value
to find the matching structured request log.

The request log contains only:

- event name and request ID;
- HTTP method and matched route template;
- response status and elapsed milliseconds.

It intentionally excludes raw paths, query strings, request/response bodies,
access tokens, user IDs, workspace IDs, document names, retrieved chunks, and
model prompts. Route templates such as `/documents/{document_id}` prevent both
sensitive UUID leakage and unbounded metric-label cardinality.

## Metrics

`GET /metrics` uses the Prometheus text format and requires an independent
bearer token stored as `OBSERVABILITY_METRICS_TOKEN`. When no token is
configured the endpoint returns `503`; missing or invalid credentials return
`401`.

The initial metrics are:

- `devatlas_http_requests_total{method,route,status_code}`;
- `devatlas_http_request_duration_seconds{method,route}`;
- `devatlas_workflow_operations_total{workflow,outcome}`.

Workflow and outcome values come from a bounded server-controlled vocabulary.
They expose search result presence, evidence sufficiency, corrective-query
branches, agent stop reasons, tool-call outcomes, and provider/contract failure
classes without recording content. Each workflow event also carries the same
request ID as its HTTP completion event, providing a lightweight correlated
trace without a separate tracing backend.

For an operator snapshot through the public CloudFront route:

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $OBSERVABILITY_METRICS_TOKEN" \
  "https://YOUR_DISTRIBUTION.cloudfront.net/api/metrics"
```

Production setup generates the token once, stores it as an encrypted SSM
SecureString, and reuses it across deployments. Do not use a Cognito access
token for this endpoint and do not place the metrics token in the frontend.

## Initial service objectives

These are operating targets, not measured performance claims:

- During intentionally scheduled demo uptime, at least 99% of HTTP requests
  should finish without a 5xx response over a rolling 30-day window.
- The p95 latency of `/health`, `/session`, and metadata list routes should stay
  below one second when the EC2 instance is warm.
- Provider-unavailable and invalid-provider-response outcomes should be
  investigated when they exceed 2% of an AI workflow over at least 20 requests;
  smaller samples are reported as incidents, not percentages.
- A CloudFront 5xx rate of at least 5% for ten minutes pages the operations SNS
  topic. EC2 instance-status failure has a separate ten-minute alarm.

The thresholds favor useful demo diagnostics over noisy alerts. The application
metrics are currently inspected on demand, so percentile and 30-day targets
cannot be claimed as continuously measured until a scraper is deployed.

## Failure and recovery workflow

1. Preserve the response `X-Request-ID`, timestamp, route, and status code.
2. Use Systems Manager Session Manager and inspect API logs with
   `docker compose logs api`; search for the request ID.
3. Compare the route's 5xx counter with its success counter and inspect the
   bounded workflow outcome (for example, `provider_unavailable`).
4. Check container health and provider status before restarting anything.
5. Retry one safe read request. A later 2xx demonstrates recovery; repeated
   failures require diagnosis rather than an unbounded retry loop.
6. If rollback is required, deploy the previous known-good revision. Database
   restoration remains a separate, explicitly confirmed procedure.

Automated tests exercise a transient 503 followed by a 200 and verify that both
outcomes remain visible. This proves telemetry convergence, not recovery from
every network, provider, database, or host failure.
