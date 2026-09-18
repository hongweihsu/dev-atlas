locals {
  name       = "${var.project_name}-${var.environment}"
  app_domain = "${var.app_subdomain}.${var.root_domain}"

  common_tags = {
    Project     = "Retrieval Works"
    Environment = var.environment
    ManagedBy   = "Terraform"
    CostCenter  = "learning-demo"
  }
}
