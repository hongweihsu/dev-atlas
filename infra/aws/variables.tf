variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform."
  type        = string
  default     = "devatlas"
}

variable "aws_region" {
  description = "AWS region for regional resources."
  type        = string
  default     = "ap-southeast-2"

  validation {
    condition     = var.aws_region == "ap-southeast-2"
    error_message = "The approved Phase 10 region is ap-southeast-2 (Sydney)."
  }
}

variable "project_name" {
  description = "Lowercase name used in resource names and tags."
  type        = string
  default     = "retrieval-works"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "demo"
}

variable "instance_type" {
  description = "ARM burstable instance sized for the low-traffic demo."
  type        = string
  default     = "t4g.small"

  validation {
    condition     = contains(["t4g.micro", "t4g.small"], var.instance_type)
    error_message = "Phase 10 permits only t4g.micro or t4g.small without a new cost review."
  }
}

variable "root_volume_gib" {
  description = "Encrypted gp3 root volume size."
  type        = number
  default     = 30

  validation {
    condition     = var.root_volume_gib >= 20 && var.root_volume_gib <= 30
    error_message = "The demo root volume must remain between 20 and 30 GiB."
  }
}

variable "monthly_budget_usd" {
  description = "Monthly AWS budget alert threshold in USD."
  type        = number
  default     = 30

  validation {
    condition     = var.monthly_budget_usd > 0 && var.monthly_budget_usd <= 30
    error_message = "The approved AWS budget may not exceed USD 30 per month."
  }
}

variable "budget_alert_email" {
  description = "Email that receives AWS Budget notifications."
  type        = string
  sensitive   = true
}
