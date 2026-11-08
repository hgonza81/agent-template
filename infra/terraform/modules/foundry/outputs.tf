output "account_id" {
  value = azurerm_cognitive_account.this.id
}

output "project_id" {
  value = azurerm_cognitive_account_project.this.id
}

output "endpoint" {
  value = azurerm_cognitive_account.this.endpoint
}

output "deployment_name" {
  value = azurerm_cognitive_deployment.model.name
}
