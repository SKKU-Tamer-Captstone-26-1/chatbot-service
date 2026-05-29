from pathlib import Path

from chatbot_service.deployment.gcp_staging_check import check_gcp_staging_artifacts

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_run_container_uses_chatbot_service_entrypoint():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'CMD ["chatbot-service"]' in dockerfile
    assert "EXPOSE 8080" in dockerfile


def test_staging_env_template_keeps_secret_values_out_of_git():
    template = (ROOT / "deploy/gcp/staging.env.yaml").read_text(encoding="utf-8")

    forbidden_secret_keys = (
        "CHATBOT_DB_DSN:",
        "CHATBOT_CACHE_REDIS_URL:",
        "HF_TOKEN:",
        "CHATBOT_VALIDATION_AUTHORIZATION:",
    )
    for key in forbidden_secret_keys:
        assert key not in template


def test_cloudbuild_pipeline_runs_migrations_before_service_deploy():
    pipeline = (ROOT / "deploy/gcp/cloudbuild.staging.yaml").read_text(encoding="utf-8")

    migration_index = pipeline.index('id: "run-migrations"')
    deploy_index = pipeline.index('id: "deploy-service"')
    assert migration_index < deploy_index
    assert "gcloud" in pipeline
    assert "jobs" in pipeline
    assert "deploy" in pipeline
    assert "--command=chatbot-migrate" in pipeline
    assert "--execute-now" in pipeline
    assert "--wait" in pipeline
    assert "--env-vars-file=deploy/gcp/staging.env.yaml" in pipeline
    assert "--set-secrets=" in pipeline
    assert "--use-http2" in pipeline
    assert ":latest" not in pipeline


def test_gcp_staging_artifact_preflight_passes():
    result = check_gcp_staging_artifacts(ROOT)

    assert result.passed is True
    assert result.checks["cloudbuild_migration_before_service"] == "ok"
    assert result.checks["staging_env_no_secret_values"] == "ok"
    assert result.checks["build_substitutions_template_required_keys"] == "ok"
    assert result.checks["secret_template_required_keys"] == "ok"
    assert result.checks["terraform_required_resources"] == "ok"
    assert result.checks["terraform_no_secret_values"] == "ok"


def test_gcp_staging_artifact_preflight_fails_when_required_file_missing(tmp_path):
    result = check_gcp_staging_artifacts(tmp_path)

    assert result.passed is False
    assert result.checks["file:Dockerfile"] == "failed: missing"


def test_validation_env_example_has_required_staging_knobs_as_placeholders():
    template = (ROOT / "deploy/gcp/staging.validation.env.example").read_text(
        encoding="utf-8"
    )

    assert "CHATBOT_VALIDATION_TARGET=REPLACE_WITH_STAGING_GATEWAY_HOST:443" in template
    assert (
        'CHATBOT_VALIDATION_AUTHORIZATION="Bearer REPLACE_WITH_STAGING_TOKEN"'
        in template
    )
    assert "CHATBOT_VALIDATION_CONCURRENCY=500" in template
    assert "CHATBOT_VALIDATION_REQUESTS=500" in template
    assert "CHATBOT_CACHE_BACKEND=redis" in template
    assert "CHATBOT_LLM_PROVIDER=huggingface_tgi" in template
    assert "HF_TOKEN=REPLACE_WITH_OPERATOR_LOCAL_TOKEN" in template


def test_build_substitutions_env_example_has_required_operator_values():
    template = (ROOT / "deploy/gcp/staging.substitutions.env.example").read_text(
        encoding="utf-8"
    )

    assert "PROJECT_ID=REPLACE_WITH_GCP_PROJECT_ID" in template
    assert "REGION=asia-northeast3" in template
    assert "REPOSITORY=REPLACE_WITH_ARTIFACT_REGISTRY_REPOSITORY" in template
    assert "CHATBOT_STAGING_SERVICE_ACCOUNT=" in template
    assert "CLOUD_SQL_CONNECTION_NAME=" in template
    assert "SERVERLESS_VPC_CONNECTOR=" in template
    assert "DB_DSN_SECRET_VERSION=REPLACE_WITH_PINNED_SECRET_VERSION" in template
    assert "REDIS_URL_SECRET_VERSION=REPLACE_WITH_PINNED_SECRET_VERSION" in template
    assert "HF_TOKEN_SECRET_VERSION=REPLACE_WITH_PINNED_SECRET_VERSION" in template


def test_secret_env_example_has_required_operator_values():
    template = (ROOT / "deploy/gcp/staging.secrets.env.example").read_text(encoding="utf-8")

    assert "PROJECT_ID=REPLACE_WITH_GCP_PROJECT_ID" in template
    assert "CHATBOT_DB_DSN=postgres://" in template
    assert "CHATBOT_CACHE_REDIS_URL=redis://" in template
    assert "HF_TOKEN=REPLACE_WITH_HUGGING_FACE_TOKEN" in template
    assert (
        'CHATBOT_VALIDATION_AUTHORIZATION="Bearer REPLACE_WITH_STAGING_VALIDATION_TOKEN"'
        in template
    )


def test_gitignore_blocks_filled_operator_env_files():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "deploy/gcp/staging.secrets.env" in gitignore
    assert "deploy/gcp/staging.substitutions.env" in gitignore
    assert "deploy/gcp/staging.validation.env" in gitignore


def test_gcp_staging_runbook_records_required_acceptance_gates():
    runbook = (ROOT / "docs/deployment/gcp-staging.md").read_text(encoding="utf-8")

    assert "deploy/gcp/cloudbuild.staging.yaml" in runbook
    assert "infra/gcp/staging" in runbook
    assert "deploy/gcp/staging.secrets.env.example" in runbook
    assert "deploy/gcp/staging.substitutions.env.example" in runbook
    assert "deploy/gcp/staging.validation.env.example" in runbook
    assert "chatbot-validate preflight" in runbook
    assert "chatbot-validate smoke" in runbook
    assert "chatbot-validate load" in runbook
    assert "chatbot-migrate" in runbook
    assert "--use-http2" in runbook


def test_terraform_scaffold_defines_base_staging_resources_without_secret_values():
    main_tf = (ROOT / "infra/gcp/staging/main.tf").read_text(encoding="utf-8")
    variables_tf = (ROOT / "infra/gcp/staging/variables.tf").read_text(encoding="utf-8")
    outputs_tf = (ROOT / "infra/gcp/staging/outputs.tf").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "google_sql_database_instance" in main_tf
    assert "database_version    = \"POSTGRES_16\"" in main_tf
    assert "ipv4_enabled    = false" in main_tf
    assert "google_redis_instance" in main_tf
    assert "connect_mode       = \"PRIVATE_SERVICE_ACCESS\"" in main_tf
    assert "google_secret_manager_secret" in main_tf
    assert "roles/run.admin" in main_tf
    assert "roles/artifactregistry.writer" in main_tf
    assert "roles/iam.serviceAccountUser" in main_tf
    assert "google_artifact_registry_repository_iam_member" in main_tf
    assert "google_service_account_iam_member" in main_tf
    assert "cloud_build_deployer_service_account_email" in variables_tf
    assert "secret_data" not in main_tf
    assert "password =" not in main_tf
    assert "cloud_sql_connection_name" in outputs_tf
    assert "cloud_build_deployer_service_account" in outputs_tf
    assert "redis_host" in outputs_tf
    assert "infra/**/*.tfvars" in gitignore
