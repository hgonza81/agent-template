variable "subscription_id" {
  description = "Azure subscription ID (supply via TF_VAR_subscription_id; never commit)."
  type        = string
}

variable "location" {
  description = "Azure region for the state backend."
  type        = string
  default     = "centralus"
}

variable "resource_group_name" {
  description = "Resource group for the state backend, separate from workloads."
  type        = string
  default     = "rg-agent-template-tfstate"
}

variable "storage_account_name" {
  description = "Globally unique storage account name (3-24 lowercase letters/digits)."
  type        = string
  default     = "stagenttemplatetfstate"

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Use 3-24 lowercase letters and digits."
  }
}

variable "container_name" {
  description = "Blob container holding one state blob per environment."
  type        = string
  default     = "tfstate"
}

variable "soft_delete_retention_days" {
  description = "Blob and container soft delete retention (at least 14)."
  type        = number
  default     = 14

  validation {
    condition     = var.soft_delete_retention_days >= 14 && var.soft_delete_retention_days <= 365
    error_message = "Retention must be between 14 and 365 days."
  }
}

variable "state_contributor_principal_ids" {
  description = "Map of label to Entra object ID granted Storage Blob Data Contributor on the state container."
  type        = map(string)
  default     = {}
}
