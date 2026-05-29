locals {
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  secret_ids = toset([
    "chatbot-staging-db-dsn",
    "chatbot-staging-redis-url",
    "chatbot-staging-hf-token",
    "chatbot-staging-validation-authorization",
  ])

  cloud_build_deployer_member = (
    var.cloud_build_deployer_service_account_email == ""
    ? ""
    : "serviceAccount:${var.cloud_build_deployer_service_account_email}"
  )
}

resource "google_project_service" "required" {
  for_each = local.required_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "chatbot" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_repository_name
  description   = "Staging Docker images for ai-chatbot-service."
  format        = "DOCKER"
  labels        = var.labels

  depends_on = [google_project_service.required]
}

resource "google_service_account" "chatbot_runtime" {
  project      = var.project_id
  account_id   = var.service_account_id
  display_name = "AI chatbot staging runtime"

  depends_on = [google_project_service.required]
}

resource "google_compute_network" "chatbot" {
  project                 = var.project_id
  name                    = var.network_name
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_global_address" "private_services" {
  project       = var.project_id
  name          = "${var.network_name}-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_cidr_prefix_length
  network       = google_compute_network.chatbot.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.chatbot.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]

  depends_on = [google_project_service.required]
}

resource "google_vpc_access_connector" "chatbot" {
  project       = var.project_id
  name          = var.vpc_connector_name
  region        = var.region
  network       = google_compute_network.chatbot.name
  ip_cidr_range = var.vpc_connector_cidr
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.required]
}

resource "google_sql_database_instance" "chatbot" {
  project             = var.project_id
  name                = var.cloud_sql_instance_name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true

  settings {
    tier              = var.cloud_sql_tier
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.cloud_sql_disk_size_gb
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.chatbot.id
    }

    user_labels = var.labels
  }

  depends_on = [google_service_networking_connection.private_services]
}

resource "google_sql_database" "chatbot" {
  project  = var.project_id
  name     = var.cloud_sql_database_name
  instance = google_sql_database_instance.chatbot.name
}

resource "google_redis_instance" "chatbot" {
  project            = var.project_id
  name               = var.redis_instance_name
  region             = var.region
  tier               = var.redis_tier
  memory_size_gb     = var.redis_memory_size_gb
  redis_version      = "REDIS_7_2"
  authorized_network = google_compute_network.chatbot.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  display_name       = "AI chatbot staging Redis"
  labels             = var.labels

  depends_on = [google_service_networking_connection.private_services]
}

resource "google_secret_manager_secret" "chatbot" {
  for_each = local.secret_ids

  project   = var.project_id
  secret_id = each.value
  labels    = var.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "chatbot_runtime" {
  for_each = google_secret_manager_secret.chatbot

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.chatbot_runtime.email}"
}

resource "google_project_iam_member" "chatbot_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.chatbot_runtime.email}"
}

resource "google_project_iam_member" "chatbot_vpcaccess_user" {
  project = var.project_id
  role    = "roles/vpcaccess.user"
  member  = "serviceAccount:${google_service_account.chatbot_runtime.email}"
}

resource "google_project_iam_member" "cloud_build_run_admin" {
  count = local.cloud_build_deployer_member == "" ? 0 : 1

  project = var.project_id
  role    = "roles/run.admin"
  member  = local.cloud_build_deployer_member
}

resource "google_artifact_registry_repository_iam_member" "cloud_build_artifact_writer" {
  count = local.cloud_build_deployer_member == "" ? 0 : 1

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.chatbot.repository_id
  role       = "roles/artifactregistry.writer"
  member     = local.cloud_build_deployer_member
}

resource "google_service_account_iam_member" "cloud_build_service_account_user" {
  count = local.cloud_build_deployer_member == "" ? 0 : 1

  service_account_id = google_service_account.chatbot_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.cloud_build_deployer_member
}
