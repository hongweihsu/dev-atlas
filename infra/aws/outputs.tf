output "cloudfront_url" {
  description = "Public HTTPS entry point after the frontend is deployed."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
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
