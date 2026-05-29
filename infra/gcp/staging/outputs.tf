output "artifact_repository" {
  description = "Artifact Registry Docker repository ID."
  value       = google_artifact_registry_repository.chatbot.repository_id
}

output "cloud_run_service_account" {
  description = "Cloud Run runtime service account email."
  value       = google_service_account.chatbot_runtime.email
}

output "cloud_build_deployer_service_account" {
  description = "Cloud Build deployer service account email when configured."
  value       = var.cloud_build_deployer_service_account_email
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name for Cloud Run attachment."
  value       = google_sql_database_instance.chatbot.connection_name
}

output "cloud_sql_database_name" {
  description = "Chatbot-owned PostgreSQL database name."
  value       = google_sql_database.chatbot.name
}

output "redis_host" {
  description = "Memorystore Redis host for the secret value."
  value       = google_redis_instance.chatbot.host
}

output "redis_port" {
  description = "Memorystore Redis port for the secret value."
  value       = google_redis_instance.chatbot.port
}

output "secret_names" {
  description = "Secret Manager secret names that require operator-supplied versions."
  value       = sorted(keys(google_secret_manager_secret.chatbot))
}

output "vpc_connector_name" {
  description = "Serverless VPC Access connector name."
  value       = google_vpc_access_connector.chatbot.name
}
