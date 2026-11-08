terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

# Azure AI Foundry resource (AIServices) with project management enabled.
# No keys: local auth is disabled, callers use Entra (RBAC) only.
resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_134:The API runs locally in Phase A and needs the public endpoint; keys are disabled, Entra RBAC only
  #checkov:skip=CKV2_AZURE_22:Microsoft-managed keys; no Key Vault in this design
  name                = var.account_name
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags

  kind                       = "AIServices"
  sku_name                   = "S0"
  custom_subdomain_name      = var.account_name
  project_management_enabled = true
  local_auth_enabled         = false

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_account_project" "this" {
  name                 = var.project_name
  cognitive_account_id = azurerm_cognitive_account.this.id
  location             = var.location
  tags                 = var.tags

  identity {
    type = "SystemAssigned"
  }
}

# One deployment only; capacity (thousands of tokens per minute) is capped.
resource "azurerm_cognitive_deployment" "model" {
  name                   = var.deployment_name
  version_upgrade_option = "NoAutoUpgrade"
  cognitive_account_id   = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }

  sku {
    name     = var.sku_name
    capacity = var.capacity
  }
}
