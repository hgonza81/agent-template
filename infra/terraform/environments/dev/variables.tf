variable "subscription_id" {
  description = "Azure subscription ID (supply via TF_VAR_subscription_id; never commit)."
  type        = string
}

variable "location" {
  description = "Azure region for every dev resource."
  type        = string
  default     = "centralus"
}

variable "model_version" {
  description = "gpt-5.4-nano version."
  type        = string
  default     = "2026-03-17"
}

variable "budget_start_date" {
  description = "First day of the month the budget starts, RFC 3339."
  type        = string
  default     = "2026-11-01T00:00:00Z"
}

variable "budget_contact_emails" {
  description = "Budget alert recipients (supply via a git-ignored tfvars file)."
  type        = list(string)
}
