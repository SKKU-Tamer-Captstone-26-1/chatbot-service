from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from chatbot_service.deployment.gcp_staging_secrets import load_env_file


class CommandRunner(Protocol):
    def __call__(self, cmd: list[str]) -> subprocess.CompletedProcess[bytes]: ...


@dataclass(frozen=True)
class CloudBuildDeployPlan:
    project_id: str
    dry_run: bool
    command: list[str]
    submitted: bool


SUBSTITUTION_ENV_TO_CLOUDBUILD = (
    ("REGION", "_REGION"),
    ("REPOSITORY", "_REPOSITORY"),
    ("SERVICE_NAME", "_SERVICE_NAME"),
    ("MIGRATION_JOB_NAME", "_MIGRATION_JOB_NAME"),
    ("CHATBOT_STAGING_SERVICE_ACCOUNT", "_SERVICE_ACCOUNT"),
    ("CLOUD_SQL_CONNECTION_NAME", "_CLOUD_SQL_CONNECTION_NAME"),
    ("SERVERLESS_VPC_CONNECTOR", "_SERVERLESS_VPC_CONNECTOR"),
    ("AUTH_SERVICE_URL", "_AUTH_SERVICE_URL"),
    ("RECOMMENDATION_SERVICE_GRPC_ADDR", "_RECOMMENDATION_SERVICE_GRPC_ADDR"),
    ("RECOMMENDATION_SERVICE_GRPC_TLS", "_RECOMMENDATION_SERVICE_GRPC_TLS"),
    ("CHATBOT_LLM_ENDPOINT_URL", "_CHATBOT_LLM_ENDPOINT_URL"),
    ("CHATBOT_LLM_MODEL", "_CHATBOT_LLM_MODEL"),
    ("CHATBOT_LLM_AUTH_MODE", "_CHATBOT_LLM_AUTH_MODE"),
    ("DB_DSN_SECRET_VERSION", "_DB_DSN_SECRET_VERSION"),
    ("REDIS_URL_SECRET_VERSION", "_REDIS_URL_SECRET_VERSION"),
    ("HF_TOKEN_SECRET_VERSION", "_HF_TOKEN_SECRET_VERSION"),
)

PINNED_SECRET_VERSION_KEYS = (
    "DB_DSN_SECRET_VERSION",
    "REDIS_URL_SECRET_VERSION",
    "HF_TOKEN_SECRET_VERSION",
)


def build_cloudbuild_submit_command(
    values: dict[str, str],
    *,
    config_path: Path = Path("deploy/gcp/cloudbuild.staging.yaml"),
    allow_placeholders: bool = False,
) -> list[str]:
    project_id = _required(values, "PROJECT_ID", allow_placeholders=allow_placeholders)
    substitutions = []
    for env_key, cloudbuild_key in SUBSTITUTION_ENV_TO_CLOUDBUILD:
        value = _required(values, env_key, allow_placeholders=allow_placeholders)
        if env_key in PINNED_SECRET_VERSION_KEYS:
            _validate_pinned_secret_version(env_key, value, allow_placeholders=allow_placeholders)
        substitutions.append(f"{cloudbuild_key}={value}")

    return [
        "gcloud",
        "builds",
        "submit",
        "--project",
        project_id,
        "--config",
        str(config_path),
        "--substitutions",
        ",".join(substitutions),
    ]


def submit_cloudbuild(
    values: dict[str, str],
    *,
    dry_run: bool = False,
    allow_placeholders: bool = False,
    config_path: Path = Path("deploy/gcp/cloudbuild.staging.yaml"),
    runner: CommandRunner | None = None,
) -> CloudBuildDeployPlan:
    command = build_cloudbuild_submit_command(
        values,
        config_path=config_path,
        allow_placeholders=allow_placeholders,
    )
    submitted = False
    if not dry_run:
        runner = runner or _run_gcloud
        runner(command)
        submitted = True
    return CloudBuildDeployPlan(
        project_id=values["PROJECT_ID"],
        dry_run=dry_run,
        command=command,
        submitted=submitted,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Submit the GCP staging Cloud Build deploy")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("deploy/gcp/staging.substitutions.env"),
        help="Ignored operator-local env file containing Cloud Build substitutions.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("deploy/gcp/cloudbuild.staging.yaml"),
        help="Cloud Build config path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the planned gcloud builds submit command.",
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow REPLACE_WITH placeholders. Intended only for checking templates.",
    )
    args = parser.parse_args(argv)

    values = load_env_file(args.env_file)
    result = submit_cloudbuild(
        values,
        dry_run=args.dry_run,
        allow_placeholders=args.allow_placeholders,
        config_path=args.config,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


def _required(values: dict[str, str], key: str, *, allow_placeholders: bool) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    if not allow_placeholders and _looks_like_placeholder(value):
        raise ValueError(f"{key} still has a placeholder value")
    return value


def _validate_pinned_secret_version(
    key: str,
    value: str,
    *,
    allow_placeholders: bool,
) -> None:
    if allow_placeholders and _looks_like_placeholder(value):
        return
    if value.strip().lower() == "latest":
        raise ValueError(f"{key} must use a pinned Secret Manager version, not latest")


def _looks_like_placeholder(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("REPLACE_WITH", "TODO", "CHANGE_ME"))


def _run_gcloud(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, check=True)


__all__ = [
    "CloudBuildDeployPlan",
    "PINNED_SECRET_VERSION_KEYS",
    "SUBSTITUTION_ENV_TO_CLOUDBUILD",
    "build_cloudbuild_submit_command",
    "main",
    "submit_cloudbuild",
]


if __name__ == "__main__":
    main()
