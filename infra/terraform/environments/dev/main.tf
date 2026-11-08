# Dev environment (the only Azure environment). Phase A: resource group,
# Foundry project with one capped model deployment, and a monthly budget.
# No ACR, Container Apps, PostgreSQL, or Application Insights (Phase B).

terraform {
  required_version = "~> 1.17.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 5.13.0"
    }
  }

  # Partial configuration: supply the rest at init time, e.g.
  #   terraform init -backend-config="resource_group_name=..." \
  #     -backend-config="storage_account_name=..." -backend-config="container_name=tfstate"
  backend "azurerm" {
    key              = "dev/terraform.tfstate"
    use_azuread_auth = true
  }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  # Phase A needs no provider registration; never register providers implicitly.
  resource_provider_registrations = "none"
}

locals {
  environment = "dev"
  tags = {
    project     = "agent-template"
    environment = local.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "this" {
  name     = "rg-agent-template-${local.environment}"
  location = var.location
  tags     = local.tags
}

module "foundry" {
  source = "../../modules/foundry"

  account_name        = "ai-agent-template-${local.environment}"
  project_name        = "proj-agent-template-${local.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags

  model_version = var.model_version
  sku_name      = "DataZoneStandard"
  capacity      = 10
}

module "budget" {
  source = "../../modules/budget"

  name              = "budget-agent-template-${local.environment}"
  resource_group_id = azurerm_resource_group.this.id
  amount_usd        = 10
  start_date        = var.budget_start_date
  contact_emails    = var.budget_contact_emails
}

# Data-plane access to the project for human developers (no keys exist).
resource "azurerm_role_assignment" "foundry_user" {
  for_each = var.foundry_user_principal_ids

  scope                = module.foundry.project_id
  role_definition_name = "Foundry User"
  principal_id         = each.value
}
