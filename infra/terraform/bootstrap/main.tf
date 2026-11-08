# Remote-state backend. Applied once, by a human, with LOCAL state that is never
# committed (see ../README.md). Separate from every environment.

terraform {
  required_version = "~> 1.17.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 5.13.0"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  # Phase A needs no provider registration; never register providers implicitly.
  resource_provider_registrations = "none"
  # Shared keys are disabled on the state account: use Entra for data-plane calls.
  storage_use_azuread = true
}

locals {
  tags = {
    project    = "agent-template"
    component  = "tfstate"
    managed_by = "terraform"
  }
}

resource "azurerm_resource_group" "state" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_storage_account" "state" {
  #checkov:skip=CKV_AZURE_33:No queue service is used; diagnostics logging is out of the USD 10 budget
  #checkov:skip=CKV_AZURE_59:Public network access stays on so the human operator and CI reach state; access is Entra-only, no shared keys, no public blobs
  #checkov:skip=CKV2_AZURE_33:Private endpoints are excluded for cost; Entra RBAC and TLS 1.2 apply
  #checkov:skip=CKV2_AZURE_1:Microsoft-managed keys with infrastructure encryption; no Key Vault in this design
  name                = var.storage_account_name
  resource_group_name = azurerm_resource_group.state.name
  location            = azurerm_resource_group.state.location
  tags                = local.tags

  account_kind             = "StorageV2"
  account_tier             = "Standard"
  account_replication_type = "GRS"

  https_traffic_only_enabled        = true
  min_tls_version                   = "TLS1_2"
  shared_access_key_enabled         = false
  default_to_oauth_authentication   = true
  allow_nested_items_to_be_public   = false
  local_user_enabled                = false
  infrastructure_encryption_enabled = true

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = var.soft_delete_retention_days
    }

    container_delete_retention_policy {
      days = var.soft_delete_retention_days
    }
  }
}

resource "azurerm_storage_container" "state" {
  #checkov:skip=CKV2_AZURE_21:Blob read logging is out of the USD 10 budget; state access is Entra-audited
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

# Least privilege: each environment identity gets data access on the container
# only (never the account), so dev cannot reach another environment's state.
resource "azurerm_role_assignment" "state_contributor" {
  for_each = var.state_contributor_principal_ids

  scope                = azurerm_storage_container.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}

resource "azurerm_management_lock" "state" {
  name       = "lock-tfstate-cannot-delete"
  scope      = azurerm_storage_account.state.id
  lock_level = "CanNotDelete"
  notes      = "Protects Terraform state. Remove only deliberately."
}
