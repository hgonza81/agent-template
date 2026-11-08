terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

# Alerts lag behind real spend and are NOT a hard cap.
resource "azurerm_consumption_budget_resource_group" "this" {
  name              = var.name
  resource_group_id = var.resource_group_id

  amount     = var.amount_usd
  time_grain = "Monthly"

  time_period {
    start_date = var.start_date
  }

  dynamic "notification" {
    for_each = {
      actual_50    = { threshold = 50, type = "Actual" }
      actual_80    = { threshold = 80, type = "Actual" }
      actual_100   = { threshold = 100, type = "Actual" }
      forecast_100 = { threshold = 100, type = "Forecasted" }
    }

    content {
      enabled        = true
      threshold      = notification.value.threshold
      threshold_type = notification.value.type
      operator       = "GreaterThanOrEqualTo"
      contact_emails = var.contact_emails
    }
  }
}
