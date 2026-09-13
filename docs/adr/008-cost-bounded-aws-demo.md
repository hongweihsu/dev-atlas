# ADR-008: Use a cost-bounded single-node AWS demo

- **Status:** Accepted for implementation; not deployed
- **Date:** 2026-09-14

## Context

The project needs a reproducible public demo and practical AWS experience, but
expects negligible traffic and has an AUD 50 monthly ceiling. An ALB, NAT
Gateway, RDS, and two always-on Fargate tasks would spend most of that budget on
idle fixed capacity.

## Decision

Serve the React build from private S3 through CloudFront and route `/api/*`
through the same distribution to one ARM `t4g.small` EC2 instance. Run FastAPI,
ARQ, Redis, and PostgreSQL/pgvector with Docker Compose on that host. Use an
Elastic IP for a stable origin, SSM rather than SSH, encrypted gp3 storage,
private S3 backups, mandatory cost tags, and a USD 30 monthly budget.

## Consequences

This preserves same-origin HTTPS without a purchased domain and avoids ALB,
NAT, RDS, and Fargate fixed costs. It deliberately accepts one failure domain,
shared CPU/RAM, operator-owned database recovery, and deployment downtime.
Those limits must remain visible in portfolio claims. Managed-service migration
remains possible because application persistence and queue code already use
adapter boundaries.
