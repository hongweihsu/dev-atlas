output "cloudfront_url" {
  description = "Public HTTPS entry point after the frontend is deployed."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.app.id
}

output "instance_id" {
  description = "Use this ID with AWS Systems Manager Session Manager."
  value       = aws_instance.app.id
}

output "web_bucket_name" {
  value = aws_s3_bucket.web.id
}

output "backup_bucket_name" {
  value = aws_s3_bucket.backup.id
}

output "estimated_budget_usd" {
  value = var.monthly_budget_usd
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.app.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_issuer" {
  value = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.app.id}"
}

output "cognito_authority" {
  value = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.app.id}"
}

output "cognito_domain" {
  value = "https://${aws_cognito_user_pool_domain.app.domain}.auth.${var.aws_region}.amazoncognito.com"
}
