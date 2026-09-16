#!/bin/bash
set -euo pipefail

repository_root=$(git rev-parse --show-toplevel)
terraform_directory="$repository_root/infra/aws"
profile=${AWS_PROFILE:-devatlas}
region=${AWS_REGION:-ap-southeast-2}
revision=$(git -C "$repository_root" rev-parse HEAD)
temporary_directory=$(mktemp -d)
archive="$temporary_directory/devatlas-$revision.tar.gz"
trap 'rm -rf "$temporary_directory"' EXIT

if [ -n "$(git -C "$repository_root" status --porcelain)" ]; then
  echo "Refusing to publish an artifact from a dirty worktree." >&2
  exit 1
fi

backup_bucket=$(terraform -chdir="$terraform_directory" output -raw backup_bucket_name)
artifact_uri="s3://$backup_bucket/artifacts/devatlas-$revision.tar.gz"

git -C "$repository_root" archive --format=tar.gz --output="$archive" HEAD
checksum=$(shasum -a 256 "$archive" | awk '{print $1}')
aws s3 cp "$archive" "$artifact_uri" \
  --profile "$profile" \
  --region "$region" \
  --sse AES256 >/dev/null

echo "ARTIFACT_URI=$artifact_uri"
echo "ARTIFACT_SHA256=$checksum"
echo "ARTIFACT_REVISION=$revision"
