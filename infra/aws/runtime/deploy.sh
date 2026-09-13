#!/bin/bash
set -euo pipefail

repository_root=$(git rev-parse --show-toplevel)
runtime_directory="$repository_root/infra/aws/runtime"

cd "$repository_root"
git pull --ff-only origin main

cd "$runtime_directory"
./render-env.sh /devatlas/demo .env
docker compose --env-file .env -f compose.yml build
docker compose --env-file .env -f compose.yml run --rm migrate
docker compose --env-file .env -f compose.yml up -d --remove-orphans
sudo ./install-backup-timer.sh
docker compose --env-file .env -f compose.yml ps
