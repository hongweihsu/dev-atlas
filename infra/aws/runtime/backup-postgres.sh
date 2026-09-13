#!/bin/bash
set -euo pipefail

runtime_directory=$(cd "$(dirname "$0")" && pwd)
cd "$runtime_directory"

set -a
source .env
set +a

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_directory="$runtime_directory/backups"
backup_path="$backup_directory/devatlas-$timestamp.dump"
mkdir -p "$backup_directory"

docker compose --env-file .env -f compose.yml exec -T postgres \
  pg_dump --format=custom --username="$POSTGRES_USER" "$POSTGRES_DB" \
  > "$backup_path"

aws s3 cp "$backup_path" "s3://$BACKUP_BUCKET/postgres/$(basename "$backup_path")"
rm -f "$backup_path"
