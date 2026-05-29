variable "project_id" {
  description = "GCP project ID for chatbot staging."
  type        = string
}

variable "region" {
  description = "Primary GCP region for chatbot staging."
  type        = string
  default     = "asia-northeast3"
}

variable "environment" {
  description = "Environment label."
  type        = string
  default     = "staging"
}

variable "artifact_repository_name" {
  description = "Artifact Registry Docker repository name."
  type        = string
  default     = "ontheblock-chatbot"
}

variable "service_account_id" {
  description = "Cloud Run service account ID."
  type        = string
  default     = "ai-chatbot-staging"
}

variable "cloud_build_deployer_service_account_email" {
  description = "Optional Cloud Build deployer service account email that should be allowed to push images and deploy the staging service."
  type        = string
  default     = ""
}

variable "network_name" {
  description = "Dedicated VPC network name for chatbot staging."
  type        = string
  default     = "chatbot-staging"
}

variable "vpc_connector_name" {
  description = "Serverless VPC Access connector name."
  type        = string
  default     = "chatbot-staging"
}

variable "vpc_connector_cidr" {
  description = "CIDR range for the Serverless VPC Access connector."
  type        = string
  default     = "10.8.0.0/28"
}

variable "private_service_cidr_prefix_length" {
  description = "Prefix length for Private Service Access allocation."
  type        = number
  default     = 16
}

variable "cloud_sql_instance_name" {
  description = "Cloud SQL PostgreSQL instance name."
  type        = string
  default     = "chatbot-staging-postgres"
}

variable "cloud_sql_database_name" {
  description = "Chatbot-owned Cloud SQL database name."
  type        = string
  default     = "chatbot_service"
}

variable "cloud_sql_tier" {
  description = "Cloud SQL machine tier for staging."
  type        = string
  default     = "db-custom-1-3840"
}

variable "cloud_sql_disk_size_gb" {
  description = "Cloud SQL disk size in GB."
  type        = number
  default     = 20
}

variable "redis_instance_name" {
  description = "Memorystore Redis instance name."
  type        = string
  default     = "chatbot-staging-redis"
}

variable "redis_memory_size_gb" {
  description = "Memorystore Redis memory size in GB."
  type        = number
  default     = 1
}

variable "redis_tier" {
  description = "Memorystore Redis tier for staging."
  type        = string
  default     = "BASIC"
}

variable "labels" {
  description = "Labels applied to supported staging resources."
  type        = map(string)
  default = {
    app         = "ai-chatbot-service"
    environment = "staging"
    managed_by  = "terraform"
  }
}
