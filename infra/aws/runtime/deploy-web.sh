#!/bin/bash
set -euo pipefail

repository_root=$(git rev-parse --show-toplevel)
terraform_directory="$repository_root/infra/aws"

cloudfront_url=$(terraform -chdir="$terraform_directory" output -raw cloudfront_url)
distribution_id=$(terraform -chdir="$terraform_directory" output -raw cloudfront_distribution_id)
web_bucket=$(terraform -chdir="$terraform_directory" output -raw web_bucket_name)

export VITE_COGNITO_AUTHORITY
export VITE_COGNITO_CLIENT_ID
export VITE_COGNITO_DOMAIN
export VITE_WORKSPACE_ID="00000000-0000-4000-8000-000000000002"
VITE_COGNITO_AUTHORITY=$(terraform -chdir="$terraform_directory" output -raw cognito_authority)
VITE_COGNITO_CLIENT_ID=$(terraform -chdir="$terraform_directory" output -raw cognito_client_id)
VITE_COGNITO_DOMAIN=$(terraform -chdir="$terraform_directory" output -raw cognito_domain)

cd "$repository_root/apps/web"
pnpm install --frozen-lockfile
pnpm build
aws s3 sync dist/ "s3://$web_bucket/" --delete --profile devatlas --region ap-southeast-2
aws cloudfront create-invalidation \
  --distribution-id "$distribution_id" \
  --paths '/*' \
  --profile devatlas >/dev/null

echo "Published DevAtlas web app to $cloudfront_url"
