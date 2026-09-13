# AWS demo operations runbook

This runbook describes the implemented Phase 10 deployment tooling. Commands
that mutate AWS or restore data require a separate operator decision.

## Deploy or update the application

On the EC2 instance, connect through Systems Manager Session Manager and run:

```bash
cd /opt/devatlas/infra/aws/runtime
./deploy.sh
```

The script fast-forwards `main`, renders a mode-600 `.env` from the
`/devatlas/demo` SSM path, builds the API image, runs Alembic to `head`, then
starts API, ARQ worker, Redis, and PostgreSQL. A migration failure stops the
rollout before API/worker replacement.

## Inspect runtime state

```bash
cd /opt/devatlas/infra/aws/runtime
docker compose --env-file .env -f compose.yml ps
docker compose --env-file .env -f compose.yml logs --tail=100 api worker
systemctl status devatlas-backup.timer
```

No PostgreSQL or Redis port is published by the production Compose file.

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
