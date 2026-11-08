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

variable "foundry_user_principal_ids" {
  description = "Map of label to Entra object ID granted Azure AI User on the Foundry project (local development with az login)."
  type        = map(string)
  default     = {}
}

variable "monitoring_daily_cap_gb" {
  description = "Daily ingestion cap for Log Analytics and Application Insights (cost guard, ADR 0002)."
  type        = number
  default     = 0.1
}

variable "api_image" {
  description = "API image in GitHub Container Registry, pinned by tag or digest. The default is a public placeholder for the first apply only."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "web_image" {
  description = "Web image in GitHub Container Registry, pinned by tag or digest. The default is a public placeholder for the first apply only."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "ghcr_username" {
  description = "GitHub user that owns the read-only registry token."
  type        = string
}

variable "ghcr_read_token" {
  description = "GitHub token with only read:packages (Container Apps secret; supply via TF_VAR_ghcr_read_token, never commit)."
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Supabase session-pooler URL, postgresql+psycopg://... (Container Apps secret; supply via TF_VAR_database_url, never commit)."
  type        = string
  sensitive   = true
}

variable "oidc_issuer" {
  description = "Entra External ID issuer. Blank until the tenant exists (API returns 503 on protected routes)."
  type        = string
  default     = ""
}

variable "oidc_discovery_url" {
  description = "Entra OIDC discovery URL. Blank until the tenant exists."
  type        = string
  default     = ""
}

variable "oidc_audience" {
  description = "Expected token audience. Blank until the tenant exists."
  type        = string
  default     = ""
}

variable "oidc_required_scope" {
  description = "Required token scope. Blank until the tenant exists."
  type        = string
  default     = ""
}
