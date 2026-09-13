aws_profile        = "devatlas"
aws_region         = "ap-southeast-2"
environment        = "demo"
instance_type      = "t4g.small"
root_volume_gib    = 30
monthly_budget_usd = 30

# Supply this at plan/apply time instead of committing a personal address:
# terraform plan -var-file=dev.tfvars -var='budget_alert_email=you@example.com'
