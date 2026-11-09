# Phase B monitoring (ADR 0002, ADR 0010): Log Analytics plus a workspace-based
# Application Insights, both with a low daily cap so ingestion cannot become a
# fixed cost. The API exports allowlisted traces and metrics to Application
# Insights (ADR 0019); it never sends chat content, prompts or responses.
# Access: no role is granted to people here; the subscription Owner already
# has access, and the API only holds the connection string (ingestion only).

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-agent-template-${local.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = var.monitoring_daily_cap_gb
  tags                = local.tags
}

resource "azurerm_application_insights" "this" {
  name                 = "appi-agent-template-${local.environment}"
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  workspace_id         = azurerm_log_analytics_workspace.this.id
  application_type     = "web"
  retention_in_days    = 30
  daily_data_cap_in_gb = var.monitoring_daily_cap_gb
  tags                 = local.tags
}

# Alerts (ADR 0019): one email action group and two metric alerts on the API
# Container App, about USD 0.10/month each.
resource "azurerm_monitor_action_group" "ops" {
  name                = "ag-agent-template-${local.environment}-ops"
  resource_group_name = azurerm_resource_group.this.name
  short_name          = "agtmplops"
  tags                = local.tags

  dynamic "email_receiver" {
    for_each = { for index, email in var.budget_contact_emails : tostring(index) => email }
    content {
      name          = "operator-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }
}

resource "azurerm_monitor_metric_alert" "api_5xx" {
  name                = "alert-agent-template-${local.environment}-api-5xx"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_container_app.api.id]
  description         = "The API returned more than 5 server errors (5xx) in 15 minutes."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5

    dimension {
      name     = "statusCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops.id
  }
}

resource "azurerm_monitor_metric_alert" "api_restarts" {
  name                = "alert-agent-template-${local.environment}-api-restarts"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_container_app.api.id]
  description         = "The API container restarted more than 3 times in 15 minutes (crash loop)."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "RestartCount"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 3
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops.id
  }
}
