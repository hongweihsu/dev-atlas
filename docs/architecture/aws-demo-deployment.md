# AWS demo deployment

## Goal and budget

Phase 10 targets an always-available learning demo in Sydney with a user limit
of AUD 50 per month and an AWS budget of USD 30. The architecture optimizes for
explainability and cost control rather than high availability.

## Planned topology

```text
Browser
  |
  v
CloudFront default HTTPS domain
  ├── /*       -> private S3 bucket -> React assets
  └── /api/*   -> CloudFront Function removes /api
                     |
                     v
                 Elastic IP
                     |
                     v
               t4g.small EC2
               Docker Compose
               ├── FastAPI :8000
               ├── ARQ worker
               ├── Redis
               └── PostgreSQL + pgvector
```

There is no inbound SSH rule. AWS Systems Manager Session Manager uses the EC2
instance role for administration. Port 8000 accepts only the AWS-managed
CloudFront origin-facing prefix list. PostgreSQL and Redis remain internal to
the Docker network.

## Cost gate

Prices were queried from the official AWS Price List API on 2026-09-14 for
`ap-southeast-2`:

| Item | Unit price | 30-day planning amount |
| --- | ---: | ---: |
| Linux `t4g.small` On-Demand | USD 0.0212/hour | USD 15.48 |
| gp3 storage | USD 0.096/GB-month | USD 2.88 for 30 GiB |
| Public IPv4, S3, CloudFront, snapshots, and logs | variable | reserve remaining budget |

Terraform refuses instance types above `t4g.small`, root disks above 30 GiB,
or a configured budget above USD 30 without a code change and review. Budget
alerts trigger at 50% actual, 80% forecast, and 100% actual. An AWS Budget is a
notification control, not a guaranteed resource kill switch.

## Explicit trade-offs

- EC2 is a single point of failure and deploys may cause downtime.
- PostgreSQL backup to private S3 and a tested restore procedure are required
  before treating the instance as the source of retained demo data.
- The root volume is deleted with the instance to avoid surprise orphan-volume
  charges; durable recovery must come from backups, not an abandoned disk.
- CloudFront provides a stable HTTPS URL without buying a domain or running an
  Application Load Balancer.
- The public EC2 subnet avoids a NAT Gateway. Security groups deny arbitrary
  inbound traffic, but outbound model-provider access remains allowed.

## Runtime and recovery implementation

The production Compose definition does not mount source code or expose database
ports. It enables Redis AOF persistence, waits for PostgreSQL/Redis health,
runs Alembic as a deployment gate, and starts Uvicorn without development
reload. EC2 reads runtime secrets from `/devatlas/demo` in SSM through its
instance role.

A daily systemd timer creates a PostgreSQL custom-format dump and uploads it to
the private backup bucket. Restore requires an exact object URI and explicit
`CONFIRM_RESTORE=yes`, stops API and worker, validates the archive, restores,
reapplies migrations, and restarts the services. These procedures remain
unverified until a disposable AWS restore rehearsal succeeds.
