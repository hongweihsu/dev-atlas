#!/bin/bash
set -euo pipefail

script_directory=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repository_root=$(cd "$script_directory/../../.." && pwd)
runtime_directory="$script_directory"

if [ -d "$repository_root/.git" ]; then
  git -C "$repository_root" pull --ff-only origin main
else
  echo "Deploying immutable source artifact without a Git checkout."
fi

cd "$runtime_directory"
./render-env.sh /devatlas/demo .env
docker compose --env-file .env -f compose.yml build
docker compose --env-file .env -f compose.yml run --rm migrate
docker compose --env-file .env -f compose.yml up -d --remove-orphans
sudo ./install-backup-timer.sh
docker compose --env-file .env -f compose.yml ps
