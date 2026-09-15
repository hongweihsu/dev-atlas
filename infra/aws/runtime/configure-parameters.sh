#!/bin/bash
set -euo pipefail

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "Set OPENAI_API_KEY in this shell before configuring production." >&2
  exit 1
fi

repository_root=$(git rev-parse --show-toplevel)
terraform_directory="$repository_root/infra/aws"
profile=${AWS_PROFILE:-devatlas}
region=${AWS_REGION:-ap-southeast-2}
parameter_path=/devatlas/demo
user_pool_id=$(terraform -chdir="$terraform_directory" output -raw cognito_user_pool_id)
client_id=$(terraform -chdir="$terraform_directory" output -raw cognito_client_id)
backup_bucket=$(terraform -chdir="$terraform_directory" output -raw backup_bucket_name)
issuer="https://cognito-idp.$region.amazonaws.com/$user_pool_id"

postgres_password=$(aws ssm get-parameter \
  --name "$parameter_path/POSTGRES_PASSWORD" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text \
  --profile "$profile" \
  --region "$region" 2>/dev/null || true)
if [ -z "$postgres_password" ]; then
  postgres_password=$(openssl rand -hex 24)
  echo "Generated the initial PostgreSQL password."
else
  echo "Reusing the existing PostgreSQL password from SSM."
fi

metrics_token=$(aws ssm get-parameter \
  --name "$parameter_path/OBSERVABILITY_METRICS_TOKEN" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text \
  --profile "$profile" \
  --region "$region" 2>/dev/null || true)
if [ -z "$metrics_token" ]; then
  metrics_token=$(openssl rand -hex 32)
  echo "Generated the initial observability metrics token."
else
  echo "Reusing the existing observability metrics token from SSM."
fi

put_parameter() {
  local name=$1
  local value=$2
  local type=${3:-String}
  aws ssm put-parameter \
    --name "$parameter_path/$name" \
    --value "$value" \
    --type "$type" \
    --overwrite \
    --profile "$profile" \
    --region "$region" >/dev/null
}

put_parameter POSTGRES_DB devatlas
put_parameter POSTGRES_USER devatlas
put_parameter POSTGRES_PASSWORD "$postgres_password" SecureString
put_parameter DATABASE_URL "postgresql+asyncpg://devatlas:$postgres_password@postgres:5432/devatlas" SecureString
put_parameter REDIS_URL redis://redis:6379/0
put_parameter OPENAI_API_KEY "$OPENAI_API_KEY" SecureString
put_parameter EMBEDDING_MODEL text-embedding-3-small
put_parameter EMBEDDING_DIMENSION 1536
put_parameter ANSWER_MODEL gpt-4.1-mini
put_parameter AUTH_DEVELOPMENT_MODE false
put_parameter AUTH_JWKS_URL "$issuer/.well-known/jwks.json"
put_parameter AUTH_JWT_ISSUER "$issuer"
put_parameter AUTH_JWT_AUDIENCE "$client_id"
put_parameter AUTH_COGNITO_CLIENT_ID "$client_id"
put_parameter OBSERVABILITY_METRICS_TOKEN "$metrics_token" SecureString
put_parameter BACKUP_BUCKET "$backup_bucket"

echo "Stored encrypted production configuration under $parameter_path."
