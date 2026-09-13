#!/bin/bash
set -euo pipefail

if [ "${CONFIRM_RESTORE:-}" != "yes" ]; then
  echo "Refusing destructive restore. Set CONFIRM_RESTORE=yes explicitly." >&2
  exit 1
fi

if [ "$#" -ne 1 ] || [[ "$1" != s3://*/postgres/*.dump ]]; then
  echo "Usage: CONFIRM_RESTORE=yes $0 s3://bucket/postgres/file.dump" >&2
  exit 1
fi

runtime_directory=$(cd "$(dirname "$0")" && pwd)
cd "$runtime_directory"

set -a
source .env
set +a

temporary_directory=$(mktemp -d)
trap 'rm -rf "$temporary_directory"' EXIT
backup_path="$temporary_directory/restore.dump"

aws s3 cp "$1" "$backup_path"
docker compose --env-file .env -f compose.yml exec -T postgres \
  pg_restore --list < "$backup_path" > /dev/null

docker compose --env-file .env -f compose.yml stop api worker
docker compose --env-file .env -f compose.yml exec -T postgres \
  pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --username="$POSTGRES_USER" \
  --dbname="$POSTGRES_DB" \
  < "$backup_path"
docker compose --env-file .env -f compose.yml run --rm migrate
docker compose --env-file .env -f compose.yml up -d api worker
