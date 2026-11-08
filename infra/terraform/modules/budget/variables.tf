variable "name" {
  type = string
}

variable "resource_group_id" {
  type = string
}

variable "amount_usd" {
  description = "Monthly budget in USD."
  type        = number
}

variable "start_date" {
  description = "First day of a month, RFC 3339 (e.g. 2026-11-01T00:00:00Z)."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-01T00:00:00Z$", var.start_date))
    error_message = "start_date must be the first day of a month at 00:00:00Z."
  }
}

variable "contact_emails" {
  description = "Alert recipients."
  type        = list(string)

  validation {
    condition     = length(var.contact_emails) > 0
    error_message = "At least one contact email is required."
  }
}
