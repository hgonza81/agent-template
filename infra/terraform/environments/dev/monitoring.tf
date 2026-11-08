# Phase B monitoring (ADR 0002, ADR 0010): Log Analytics plus a workspace-based
# Application Insights, both with a low daily cap so ingestion cannot become a
# fixed cost. Nothing here receives prompts or responses: the API never logs
# chat content and Application Insights is not wired to the API yet.

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
