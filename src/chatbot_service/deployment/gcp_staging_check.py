from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class GcpStagingArtifactCheck:
    passed: bool
    checks: dict[str, str]


REQUIRED_FILES = (
    "Dockerfile",
    "deploy/gcp/staging.env.yaml",
    "deploy/gcp/cloudbuild.staging.yaml",
    "deploy/gcp/staging.substitutions.env.example",
    "deploy/gcp/staging.validation.env.example",
    "docs/deployment/gcp-staging.md",
    "infra/gcp/staging/README.md",
    "infra/gcp/staging/main.tf",
    "infra/gcp/staging/outputs.tf",
    "infra/gcp/staging/variables.tf",
    "infra/gcp/staging/versions.tf",
)

REQUIRED_NON_SECRET_ENV_KEYS = (
    "RECOMMENDATION_SERVICE_URL:",
    "CHATBOT_LLM_PROVIDER:",
    "CHATBOT_LLM_ENDPOINT_URL:",
    "CHATBOT_LLM_MODEL:",
    "CHATBOT_CACHE_BACKEND:",
    "CHATBOT_STORE_CONVERSATIONS:",
)

FORBIDDEN_STAGING_ENV_KEYS = (
    "CHATBOT_DB_DSN:",
    "CHATBOT_CACHE_REDIS_URL:",
    "HF_TOKEN:",
    "CHATBOT_VALIDATION_AUTHORIZATION:",
)

REQUIRED_PIPELINE_TOKENS = (
    'id: "build-image"',
    'id: "push-image"',
    'id: "run-migrations"',
    'id: "deploy-service"',
    "--command=chatbot-migrate",
    "--execute-now",
    "--wait",
    "--env-vars-file=deploy/gcp/staging.env.yaml",
    "--set-secrets=",
    "--set-cloudsql-instances=",
    "--vpc-connector=",
    "--use-http2",
    "--startup-probe=grpc.port=8080",
    "--no-allow-unauthenticated",
)

REQUIRED_VALIDATION_TEMPLATE_KEYS = (
    "CHATBOT_VALIDATION_TARGET=",
    "CHATBOT_VALIDATION_SECURE=true",
    "CHATBOT_VALIDATION_AUTHORIZATION=",
    "CHATBOT_VALIDATION_CONCURRENCY=500",
    "CHATBOT_VALIDATION_REQUESTS=500",
    "CHATBOT_CACHE_BACKEND=redis",
    "CHATBOT_DB_DSN=",
    "CHATBOT_LLM_PROVIDER=huggingface_tgi",
    "HF_TOKEN=",
)

REQUIRED_BUILD_SUBSTITUTION_TEMPLATE_KEYS = (
    "PROJECT_ID=",
    "REGION=",
    "REPOSITORY=",
    "SERVICE_NAME=",
    "MIGRATION_JOB_NAME=",
    "CHATBOT_STAGING_SERVICE_ACCOUNT=",
    "CLOUD_SQL_CONNECTION_NAME=",
    "SERVERLESS_VPC_CONNECTOR=",
    "DB_DSN_SECRET_VERSION=",
    "REDIS_URL_SECRET_VERSION=",
    "HF_TOKEN_SECRET_VERSION=",
)

REQUIRED_RUNBOOK_TOKENS = (
    "infra/gcp/staging",
    "deploy/gcp/cloudbuild.staging.yaml",
    "deploy/gcp/staging.substitutions.env.example",
    "deploy/gcp/staging.validation.env.example",
    "chatbot-migrate",
    "chatbot-validate preflight",
    "chatbot-validate smoke",
    "chatbot-validate load",
)

REQUIRED_TERRAFORM_MAIN_TOKENS = (
    "google_project_service",
    "google_artifact_registry_repository",
    "google_service_account",
    "google_compute_network",
    "google_vpc_access_connector",
    "google_sql_database_instance",
    "database_version    = \"POSTGRES_16\"",
    "ipv4_enabled    = false",
    "google_redis_instance",
    "connect_mode       = \"PRIVATE_SERVICE_ACCESS\"",
    "google_secret_manager_secret",
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.client",
    "roles/vpcaccess.user",
)

FORBIDDEN_TERRAFORM_SECRET_TOKENS = (
    "secret_data",
    "password =",
    "private_key",
)


def check_gcp_staging_artifacts(root: Path | None = None) -> GcpStagingArtifactCheck:
    root = root or Path(__file__).resolve().parents[3]
    checks: dict[str, str] = {}

    for relative_path in REQUIRED_FILES:
        path = root / relative_path
        checks[f"file:{relative_path}"] = "ok" if path.is_file() else "failed: missing"

    dockerfile = _read(root / "Dockerfile")
    checks["dockerfile_entrypoint"] = _contains_all(
        dockerfile,
        ('CMD ["chatbot-service"]', "EXPOSE 8080"),
    )

    staging_env = _read(root / "deploy/gcp/staging.env.yaml")
    checks["staging_env_required_keys"] = _contains_all(
        staging_env,
        REQUIRED_NON_SECRET_ENV_KEYS,
    )
    checks["staging_env_no_secret_values"] = _contains_none(
        staging_env,
        FORBIDDEN_STAGING_ENV_KEYS,
    )

    pipeline = _read(root / "deploy/gcp/cloudbuild.staging.yaml")
    checks["cloudbuild_required_steps"] = _contains_all(pipeline, REQUIRED_PIPELINE_TOKENS)
    checks["cloudbuild_migration_before_service"] = _ordered(
        pipeline,
        'id: "run-migrations"',
        'id: "deploy-service"',
    )
    checks["cloudbuild_uses_pinned_secret_versions"] = (
        "ok" if ":latest" not in pipeline else "failed: pipeline uses :latest secret version"
    )

    validation_template = _read(root / "deploy/gcp/staging.validation.env.example")
    checks["validation_template_required_keys"] = _contains_all(
        validation_template,
        REQUIRED_VALIDATION_TEMPLATE_KEYS,
    )
    checks["validation_template_placeholders"] = (
        "ok"
        if "REPLACE_WITH_" in validation_template
        else "failed: validation template should keep placeholder values"
    )

    build_substitutions_template = _read(root / "deploy/gcp/staging.substitutions.env.example")
    checks["build_substitutions_template_required_keys"] = _contains_all(
        build_substitutions_template,
        REQUIRED_BUILD_SUBSTITUTION_TEMPLATE_KEYS,
    )
    checks["build_substitutions_template_placeholders"] = (
        "ok"
        if "REPLACE_WITH_" in build_substitutions_template
        else "failed: substitutions template should keep placeholder values"
    )

    gitignore = _read(root / ".gitignore")
    checks["operator_env_ignored"] = _contains_all(
        gitignore,
        (
            "deploy/gcp/*.local.env",
            "deploy/gcp/staging.substitutions.env",
            "deploy/gcp/staging.validation.env",
        ),
    )

    runbook = _read(root / "docs/deployment/gcp-staging.md")
    checks["runbook_required_steps"] = _contains_all(runbook, REQUIRED_RUNBOOK_TOKENS)

    terraform_main = _read(root / "infra/gcp/staging/main.tf")
    checks["terraform_required_resources"] = _contains_all(
        terraform_main,
        REQUIRED_TERRAFORM_MAIN_TOKENS,
    )
    checks["terraform_no_secret_values"] = _contains_none(
        terraform_main,
        FORBIDDEN_TERRAFORM_SECRET_TOKENS,
    )

    terraform_readme = _read(root / "infra/gcp/staging/README.md")
    checks["terraform_readme_secret_policy"] = _contains_all(
        terraform_readme,
        ("does not create secret values", "Do not put DB passwords"),
    )

    return GcpStagingArtifactCheck(
        passed=all(value == "ok" for value in checks.values()),
        checks=checks,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check GCP staging deployment artifacts")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root. Defaults to the current chatbot-service checkout.",
    )
    args = parser.parse_args(argv)

    result = check_gcp_staging_artifacts(args.root)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if not result.passed:
        raise SystemExit(1)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _contains_all(text: str, required: tuple[str, ...]) -> str:
    missing = [token for token in required if token not in text]
    if missing:
        return "failed: missing " + ", ".join(missing)
    return "ok"


def _contains_none(text: str, forbidden: tuple[str, ...]) -> str:
    found = [token for token in forbidden if token in text]
    if found:
        return "failed: forbidden " + ", ".join(found)
    return "ok"


def _ordered(text: str, before: str, after: str) -> str:
    before_index = text.find(before)
    after_index = text.find(after)
    if before_index < 0:
        return f"failed: missing {before}"
    if after_index < 0:
        return f"failed: missing {after}"
    if before_index > after_index:
        return f"failed: {before} must appear before {after}"
    return "ok"


__all__ = ["GcpStagingArtifactCheck", "check_gcp_staging_artifacts", "main"]


if __name__ == "__main__":
    main()
