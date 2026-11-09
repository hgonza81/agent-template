# Phase B hosting (ADR 0002, 0005, 0009, 0010): Container Apps on the
# Consumption plan, one user-assigned identity for the API, images from GitHub
# Container Registry, secrets supplied outside git.

locals {
  api_name = "ca-agent-template-${local.environment}-api"
  web_name = "ca-agent-template-${local.environment}-web"

  # Container Apps FQDNs are deterministic: <app>.<environment default domain>.
  api_url = "https://${local.api_name}.${azurerm_container_app_environment.this.default_domain}"
  web_url = "https://${local.web_name}.${azurerm_container_app_environment.this.default_domain}"

  foundry_project_endpoint = "https://${module.foundry.account_name}.services.ai.azure.com/api/projects/${module.foundry.project_name}"
}

resource "azurerm_user_assigned_identity" "api" {
  name                = "id-agent-template-${local.environment}-api"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags
}

# Data-plane access to the project for the API (no keys exist).
resource "azurerm_role_assignment" "api_foundry_user" {
  scope                = module.foundry.project_id
  role_definition_name = "Foundry User"
  principal_id         = azurerm_user_assigned_identity.api.principal_id
}

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-agent-template-${local.environment}"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  # Consumption only: no workload profiles, no VNet, so no zone redundancy.
  tags = local.tags

  # Azure adds an implicit "Consumption" workload profile that we do not manage.
  lifecycle {
    ignore_changes = [workload_profile]
  }
}

resource "azurerm_container_app" "api" {
  name                         = local.api_name
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = local.tags

  # Azure sets an implicit "Consumption" workload profile name that we do not manage.
  # The image is deployed by CI with `az containerapp update`; Terraform must
  # not revert it (var.*_image only seeds the first apply or a recreation).
  lifecycle {
    ignore_changes = [workload_profile_name, template[0].container[0].image]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.api.id]
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = "ghcr-token"
  }

  secret {
    name  = "ghcr-token"
    value = var.ghcr_read_token
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  # Carries the instrumentation key; enables the Azure Monitor exporter in the
  # API (ADR 0019).
  secret {
    name  = "appinsights-connection-string"
    value = azurerm_application_insights.this.connection_string
  }

  # External because the browser calls the API directly; every protected route
  # validates the Entra JWT in FastAPI (ADR 0010).
  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "api"
      image  = var.api_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = jsonencode([local.web_url])
      }
      env {
        name  = "AGENT_PROVIDER"
        value = "foundry"
      }
      env {
        name  = "FOUNDRY_PROJECT_ENDPOINT"
        value = local.foundry_project_endpoint
      }
      env {
        name  = "FOUNDRY_DEPLOYMENT"
        value = module.foundry.deployment_name
      }
      # Selects the user-assigned identity for DefaultAzureCredential.
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.api.client_id
      }
      env {
        name  = "OIDC_ISSUER"
        value = var.oidc_issuer
      }
      env {
        name  = "OIDC_DISCOVERY_URL"
        value = var.oidc_discovery_url
      }
      env {
        name  = "OIDC_AUDIENCE"
        value = var.oidc_audience
      }
      env {
        name  = "OIDC_REQUIRED_SCOPE"
        value = var.oidc_required_scope
      }

      # Liveness only: it must not depend on the database or the provider.
      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/api/v1/health/live"
      }
    }
  }
}

resource "azurerm_container_app" "web" {
  name                         = local.web_name
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = local.tags

  # Azure sets an implicit "Consumption" workload profile name that we do not manage.
  # The image is deployed by CI with `az containerapp update`; Terraform must
  # not revert it (var.*_image only seeds the first apply or a recreation).
  lifecycle {
    ignore_changes = [workload_profile_name, template[0].container[0].image]
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = "ghcr-token"
  }

  secret {
    name  = "ghcr-token"
    value = var.ghcr_read_token
  }

  ingress {
    external_enabled           = true
    target_port                = 8080
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "web"
      image  = var.web_image
      cpu    = 0.25
      memory = "0.5Gi"

      liveness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/healthz"
      }
    }
  }
}

# One-shot, manually triggered Alembic migration (ADR 0017). It runs the API
# image against Supabase only: no identity (so no Azure permissions), no
# ingress, and only the settings the app requires to start.
resource "azurerm_container_app_job" "migrate" {
  name                         = "caj-agent-template-${local.environment}-migrate"
  resource_group_name          = azurerm_resource_group.this.name
  location                     = azurerm_resource_group.this.location
  container_app_environment_id = azurerm_container_app_environment.this.id
  replica_timeout_in_seconds   = 300
  replica_retry_limit          = 0
  tags                         = local.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  # The image is updated by CI before the job is started (see the README).
  lifecycle {
    ignore_changes = [workload_profile_name, template[0].container[0].image]
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = "ghcr-token"
  }

  secret {
    name  = "ghcr-token"
    value = var.ghcr_read_token
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  template {
    container {
      name    = "migrate"
      image   = var.api_image
      cpu     = 0.25
      memory  = "0.5Gi"
      command = ["alembic", "-c", "alembic.ini", "upgrade", "head"]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      # Required by the settings model even though migrations never use it.
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = jsonencode([local.web_url])
      }
    }
  }
}
