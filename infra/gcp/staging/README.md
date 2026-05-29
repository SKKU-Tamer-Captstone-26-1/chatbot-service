# GCP Staging Terraform

This scaffold provisions non-secret base resources for
`docs/plans/006-gcp-staging.md`.

It creates:

- required Google APIs
- Artifact Registry Docker repository
- Cloud Run runtime service account
- dedicated VPC and Serverless VPC Access connector
- Private Service Access allocation
- private Cloud SQL PostgreSQL instance and chatbot database
- private Memorystore Redis instance
- Secret Manager secret containers without secret versions
- runtime IAM for Cloud SQL, VPC Access, and secret access
- optional Cloud Build deployer IAM for Cloud Run deployment, Artifact Registry
  image push, and runtime service-account attachment

It does not create secret values. Add Secret Manager versions manually or through
an approved secret-loading process after `terraform apply`.

## Usage

Create an operator-local `terraform.tfvars` file. It is ignored by git.

```hcl
project_id = "REPLACE_WITH_GCP_PROJECT_ID"
region     = "asia-northeast3"

# Recommended for projects where Cloud Build runs as a dedicated deployer
# service account. This avoids relying on project-specific default behavior.
cloud_build_deployer_service_account_email = "REPLACE_WITH_CLOUD_BUILD_DEPLOYER_SA"
```

Then run:

```bash
terraform init
terraform plan
terraform apply
```

Use the outputs to fill the Cloud Build substitutions and Secret Manager values
documented in `docs/deployment/gcp-staging.md`.

## Secret Values

Create versions for these Terraform-created secrets outside Terraform:

```text
chatbot-staging-db-dsn
chatbot-staging-redis-url
chatbot-staging-hf-token
chatbot-staging-validation-authorization
```

Do not put DB passwords, Redis URLs, LLM tokens, validation tokens, or
service-account JSON files in Terraform variables or tracked files.
