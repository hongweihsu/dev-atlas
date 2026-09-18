# Retrieval Works AWS infrastructure

The configuration serves the application at `retrieval.dennishsu.dev`. The ACM
certificate is intentionally created through an aliased `us-east-1` provider
because CloudFront does not accept certificates from the Sydney region. Route
53 DNS validation and the A/AAAA aliases are managed by Terraform.

Phase 10 targets a cost-bounded portfolio deployment in `ap-southeast-2`:

```text
CloudFront
  ├── /          -> private S3 React assets
  └── /api/*     -> EC2 FastAPI (the prefix is removed at the edge)
                         |
                         +-- Docker: API, worker, Redis, PostgreSQL/pgvector
```

Terraform intentionally avoids an ALB, NAT Gateway, RDS, and always-on Fargate
tasks. Their fixed monthly cost is not justified by a low-traffic learning demo
capped at AUD 50.

## Safety boundary

`terraform plan` is read-only. `terraform apply` creates billable resources and
must not be run until the plan and estimate have been reviewed. Terraform state
can contain infrastructure metadata and stays local/ignored in this phase.

## Validate without creating resources

```bash
cd infra/aws
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=dev.tfvars -var='budget_alert_email=you@example.com'
```

The checked-in variables contain no secrets. OpenAI and production identity
settings will be written to SSM separately and never committed.

## Deployed demo status and limitations

- One EC2 instance is a documented single point of failure.
- PostgreSQL and Redis are not managed services.
- Production Compose, Cognito login, SSM runtime parameters, CloudWatch alarms,
  a protected metrics endpoint, and the daily backup timer are live on AWS.
- Backup upload and destructive restore still require a disposable recovery
  rehearsal before recovery-time claims can be made.
- Deployment uses a private, checksum-verified S3 source artifact and builds
  images on EC2; a mature pipeline would build and scan immutable images in CI.
- A budget sends alerts; it is not a guaranteed kill switch.
