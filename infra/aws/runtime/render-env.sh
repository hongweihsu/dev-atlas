#!/bin/bash
set -euo pipefail

parameter_path=${1:-/retrieval-works/demo}
target_file=${2:-.env}
temporary_file=$(mktemp)
trap 'rm -f "$temporary_file"' EXIT

aws ssm get-parameters-by-path \
  --path "$parameter_path" \
  --with-decryption \
  --recursive \
  --query 'Parameters[*].[Name,Value]' \
  --output json \
  | jq -r '.[] | "\(.[0] | split("/")[-1])=\(.[1] | @sh)"' \
  > "$temporary_file"

chmod 600 "$temporary_file"
mv "$temporary_file" "$target_file"
trap - EXIT
