variable "account_name" {
  type = string
}

variable "project_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "deployment_name" {
  type    = string
  default = "chat"
}

variable "model_name" {
  type    = string
  default = "gpt-5.4-nano"
}

variable "model_version" {
  description = "Model version; confirm the GA version with `az cognitiveservices model list` before apply."
  type        = string
}

variable "sku_name" {
  description = "Deployment type. DataZoneStandard keeps processing in the US data zone."
  type        = string
  default     = "DataZoneStandard"

  validation {
    condition     = contains(["DataZoneStandard", "GlobalStandard"], var.sku_name)
    error_message = "Use DataZoneStandard or GlobalStandard."
  }
}

variable "capacity" {
  description = "Capacity in thousands of tokens per minute; hard-capped at 10."
  type        = number
  default     = 10

  validation {
    condition     = var.capacity >= 1 && var.capacity <= 10
    error_message = "Capacity is capped at 10 (10K TPM) for the USD 10 budget."
  }
}
