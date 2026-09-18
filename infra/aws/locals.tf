locals {
  name = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = "Retrieval Works"
    Environment = var.environment
    ManagedBy   = "Terraform"
    CostCenter  = "learning-demo"
  }
}
