# AWS demo operations runbook

This runbook describes the implemented Phase 10 deployment tooling. Commands
that mutate AWS or restore data require a separate operator decision.

## Deployment order

After reviewing and explicitly approving the saved Terraform plan:

1. Apply the exact saved plan and confirm the SNS subscription email.
2. Export a newly rotated `OPENAI_API_KEY` locally and run
   `infra/aws/runtime/configure-parameters.sh`. On its first run it generates a
   random database password; later runs reuse that value. Secrets are stored as
   SSM `SecureString` values.
3. Connect through Session Manager and run `deploy.sh` on EC2.
4. Create the sole Cognito user with `aws cognito-idp admin-create-user`.
5. Read its immutable Cognito `sub`, then run `scripts/provision_identity.py`
   inside the `migrate` container to grant an explicit workspace role.
6. Run `deploy-web.sh` locally. It builds with Cognito's Terraform outputs,
   syncs the private S3 origin, and invalidates CloudFront.

Creating a Cognito user alone is intentionally insufficient. Provisioning links
the verified `(issuer, sub)` to a database workspace; rerunning it updates the
same user and membership instead of creating duplicates.

Example identity provisioning on EC2:

```bash
cd /opt/devatlas/infra/aws/runtime
docker compose --env-file .env -f compose.yml run --rm migrate \
  python scripts/provision_identity.py \
  --issuer "$AUTH_JWT_ISSUER" \
  --subject "COGNITO_SUB_FROM_ADMIN_GET_USER" \
  --email "OWNER_EMAIL" \
  --display-name "DevAtlas Owner" \
  --role owner
```

## Deploy or update the application

The repository is private, so production does not store a personal GitHub token.
Publish an immutable archive containing only files tracked by the current Git
commit:

```bash
./infra/aws/runtime/publish-artifact.sh
```

The command prints the S3 URI, SHA-256 checksum, and Git revision. Through
Systems Manager, download that exact private `artifacts/*` object with the EC2
instance role, verify its checksum, extract it into a staging directory, and
atomically replace `/opt/devatlas`. Keep the previous directory until the smoke
test passes.

EC2 bootstrap installs pinned Docker Compose and Buildx CLI plugins from
Docker's official releases and verifies both ARM64 binaries against their
published SHA-256 checksums. This is required because the Amazon Linux 2023
repository used by the demo does not currently provide a compatible Compose
package, and its bundled Buildx is older than current Compose requires.

Then run on EC2:

```bash
cd /opt/devatlas/infra/aws/runtime
./deploy.sh
```

For a Git checkout the script first fast-forwards `main`; for an immutable
artifact it skips Git. It then renders a mode-600 `.env` from the
`/devatlas/demo` SSM path, builds the API image, runs Alembic to `head`, and
starts API, ARQ worker, Redis, and PostgreSQL. A migration failure stops the
rollout before API/worker replacement.

## Inspect runtime state

```bash
cd /opt/devatlas/infra/aws/runtime
docker compose --env-file .env -f compose.yml ps
docker compose --env-file .env -f compose.yml logs --tail=100 api worker
systemctl status devatlas-backup.timer
```

Inspect privacy-bounded application metrics without exposing the operator token
to the browser:

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $OBSERVABILITY_METRICS_TOKEN" \
  http://localhost:8000/metrics
```

When a request fails, preserve its `X-Request-ID` and search both correlated
HTTP and workflow events:

```bash
docker compose --env-file .env -f compose.yml logs api \
  | grep 'REQUEST_ID_FROM_RESPONSE'
```

No PostgreSQL or Redis port is published by the production Compose file.
The React application uses Authorization Code with PKCE and keeps OIDC state in
session storage. Local development stays on the explicit development-session
endpoint unless the hosted `VITE_COGNITO_*` values are supplied.

## Backup

The deploy script installs a systemd timer for a daily PostgreSQL custom-format
dump. The temporary local dump is uploaded to the private backup bucket and
removed; S3 expires demo backups after 30 days.

Run a manual backup:

```bash
cd /opt/devatlas/infra/aws/runtime
./backup-postgres.sh
```

List retained backups:

```bash
aws s3 ls "s3://$BACKUP_BUCKET/postgres/"
```

## Restore

Restore stops API and worker, validates the dump catalog, replaces database
objects, reapplies migrations, and restarts application processes. It refuses
to run unless the operator supplies both an exact S3 dump URI and an explicit
confirmation variable:

```bash
CONFIRM_RESTORE=yes ./restore-postgres.sh \
  s3://example-backup-bucket/postgres/devatlas-YYYYMMDDTHHMMSSZ.dump
```

Always rehearse restore with disposable data before relying on backups.

## Cost incident

If a budget alert fires:

1. Inspect AWS Cost Explorer by service and usage type.
2. Check for an unexpected instance, volume, snapshot, Elastic IP, or log spike.
3. Stop the EC2 instance to stop compute billing if availability is not needed.
4. Do not delete the instance until a backup has been verified.
5. Remember that stopped compute can still leave storage and IPv4 charges.
