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
