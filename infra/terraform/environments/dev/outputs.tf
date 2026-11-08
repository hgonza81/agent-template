output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "foundry_endpoint" {
  value = module.foundry.endpoint
}

output "foundry_project_id" {
  value = module.foundry.project_id
}

output "foundry_deployment_name" {
  value = module.foundry.deployment_name
}

output "api_url" {
  value = local.api_url
}

output "web_url" {
  value = local.web_url
}

output "api_identity_client_id" {
  value = azurerm_user_assigned_identity.api.client_id
}
