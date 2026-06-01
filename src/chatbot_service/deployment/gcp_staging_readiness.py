from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from chatbot_service.deployment.gcp_staging_secrets import load_env_file


class CommandRunner(Protocol):
    def __call__(self, cmd: list[str]) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class GcpStagingReadinessResult:
    phase: str
    passed: bool
    checks: dict[str, str]


REQUIRED_OPERATOR_KEYS = (
    "PROJECT_ID",
    "REGION",
    "REPOSITORY",
    "SERVICE_NAME",
    "MIGRATION_JOB_NAME",
    "CHATBOT_STAGING_SERVICE_ACCOUNT",
    "CLOUD_SQL_CONNECTION_NAME",
    "SERVERLESS_VPC_CONNECTOR",
    "AUTH_SERVICE_URL",
    "RECOMMENDATION_SERVICE_GRPC_ADDR",
    "RECOMMENDATION_SERVICE_GRPC_TLS",
    "CHATBOT_LLM_ENDPOINT_URL",
    "CHATBOT_LLM_MODEL",
    "DB_DSN_SECRET_VERSION",
    "REDIS_URL_SECRET_VERSION",
    "HF_TOKEN_SECRET_VERSION",
)

PINNED_SECRET_VERSION_KEYS = (
    "DB_DSN_SECRET_VERSION",
    "REDIS_URL_SECRET_VERSION",
    "HF_TOKEN_SECRET_VERSION",
)

SECRET_VERSION_CHECKS = (
    ("DB_DSN_SECRET_VERSION", "chatbot-staging-db-dsn"),
    ("REDIS_URL_SECRET_VERSION", "chatbot-staging-redis-url"),
    ("HF_TOKEN_SECRET_VERSION", "chatbot-staging-hf-token"),
)

READINESS_PHASES = ("predeploy", "postdeploy")


def check_gcp_staging_readiness(
    values: dict[str, str],
    *,
    phase: str = "predeploy",
    redis_instance_name: str = "chatbot-staging-redis",
    runner: CommandRunner | None = None,
) -> GcpStagingReadinessResult:
    if phase not in READINESS_PHASES:
        raise ValueError(f"unsupported readiness phase: {phase}")

    runner = runner or _run_gcloud
    checks: dict[str, str] = {}

    for key in REQUIRED_OPERATOR_KEYS:
        checks[f"operator_env:{key}"] = _operator_value_status(
            key,
            values.get(key, ""),
            require_pinned_version=key in PINNED_SECRET_VERSION_KEYS,
        )

    project_id = values.get("PROJECT_ID", "").strip()
    region = values.get("REGION", "").strip()
    repository = values.get("REPOSITORY", "").strip()
    service_account = values.get("CHATBOT_STAGING_SERVICE_ACCOUNT", "").strip()
    connection_name = values.get("CLOUD_SQL_CONNECTION_NAME", "").strip()
    vpc_connector = values.get("SERVERLESS_VPC_CONNECTOR", "").strip()
    service_name = values.get("SERVICE_NAME", "").strip()
    sql_instance = _cloud_sql_instance_from_connection_name(connection_name)

    checks["artifact_registry"] = _check_json_object(
        _artifact_registry_command(project_id, region, repository),
        runner=runner,
        predicate=lambda payload: _has_nonempty(payload, "name"),
    )
    checks["runtime_service_account"] = _check_json_object(
        _service_account_command(project_id, service_account),
        runner=runner,
        predicate=lambda payload: payload.get("email") == service_account,
    )
    checks["vpc_connector"] = _check_json_object(
        _vpc_connector_command(project_id, region, vpc_connector),
        runner=runner,
        predicate=lambda payload: str(payload.get("state", "")).upper() == "READY",
    )
    checks["cloud_sql_instance"] = _check_json_object(
        _cloud_sql_command(project_id, sql_instance),
        runner=runner,
        predicate=lambda payload: (
            payload.get("connectionName") == connection_name
            and str(payload.get("state", "")).upper() == "RUNNABLE"
        ),
    )
    checks["redis_instance"] = _check_json_object(
        _redis_command(project_id, region, redis_instance_name),
        runner=runner,
        predicate=lambda payload: str(payload.get("state", "")).upper() == "READY",
    )

    for version_key, secret_name in SECRET_VERSION_CHECKS:
        checks[f"secret_version:{secret_name}"] = _check_secret_version(
            _secret_versions_command(project_id, secret_name),
            pinned_version=values.get(version_key, "").strip(),
            runner=runner,
        )

    if phase == "postdeploy":
        checks["cloud_run_service"] = _check_json_object(
            _cloud_run_command(project_id, region, service_name),
            runner=runner,
            predicate=_cloud_run_ready,
        )
    else:
        checks["cloud_run_service"] = "skipped: predeploy"

    return GcpStagingReadinessResult(
        phase=phase,
        passed=all(_status_passed(status) for status in checks.values()),
        checks=checks,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check live GCP staging deployment readiness")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("deploy/gcp/staging.substitutions.env"),
        help="Ignored operator-local env file containing staging substitutions.",
    )
    parser.add_argument(
        "--phase",
        choices=READINESS_PHASES,
        default="predeploy",
        help="predeploy skips Cloud Run service readiness; postdeploy requires it.",
    )
    parser.add_argument(
        "--redis-instance-name",
        default="chatbot-staging-redis",
        help="Memorystore Redis instance name to inspect.",
    )
    args = parser.parse_args(argv)

    values = load_env_file(args.env_file)
    result = check_gcp_staging_readiness(
        values,
        phase=args.phase,
        redis_instance_name=args.redis_instance_name,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if not result.passed:
        raise SystemExit(1)


def _operator_value_status(
    key: str,
    value: str,
    *,
    require_pinned_version: bool,
) -> str:
    value = value.strip()
    if not value:
        return "failed: missing"
    if _looks_like_placeholder(value):
        return "failed: placeholder"
    if require_pinned_version and value.lower() == "latest":
        return "failed: latest is not pinned"
    return "ok"


def _check_json_object(
    cmd: list[str],
    *,
    runner: CommandRunner,
    predicate: Any,
) -> str:
    status, payload = _run_json(cmd, runner=runner)
    if status != "ok":
        return status
    if not isinstance(payload, dict):
        return "failed: expected json object"
    return "ok" if predicate(payload) else "failed: unexpected state"


def _check_secret_version(
    cmd: list[str],
    *,
    pinned_version: str,
    runner: CommandRunner,
) -> str:
    if not pinned_version.strip() or _looks_like_placeholder(pinned_version):
        return "failed: pinned version missing"
    if pinned_version.strip().lower() == "latest":
        return "failed: latest is not pinned"

    status, payload = _run_json(cmd, runner=runner)
    if status != "ok":
        return status
    if not isinstance(payload, list):
        return "failed: expected json list"

    enabled_versions = {
        str(item.get("name", "")).rsplit("/", maxsplit=1)[-1]
        for item in payload
        if isinstance(item, dict) and str(item.get("state", "")).upper() == "ENABLED"
    }
    if pinned_version.strip() not in enabled_versions:
        return f"failed: version {pinned_version.strip()} is not enabled"
    return "ok"


def _run_json(cmd: list[str], *, runner: CommandRunner) -> tuple[str, Any]:
    if any(not part for part in cmd):
        return "failed: command has empty argument", None
    completed = runner(cmd)
    if completed.returncode != 0:
        return f"failed: command returned {completed.returncode}", None
    raw = completed.stdout.strip()
    if not raw:
        return "failed: empty json output", None
    try:
        return "ok", json.loads(raw)
    except json.JSONDecodeError:
        return "failed: invalid json output", None


def _run_gcloud(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _artifact_registry_command(project_id: str, region: str, repository: str) -> list[str]:
    return [
        "gcloud",
        "artifacts",
        "repositories",
        "describe",
        repository,
        "--location",
        region,
        "--project",
        project_id,
        "--format=json",
    ]


def _service_account_command(project_id: str, service_account: str) -> list[str]:
    return [
        "gcloud",
        "iam",
        "service-accounts",
        "describe",
        service_account,
        "--project",
        project_id,
        "--format=json",
    ]


def _vpc_connector_command(project_id: str, region: str, connector: str) -> list[str]:
    return [
        "gcloud",
        "compute",
        "networks",
        "vpc-access",
        "connectors",
        "describe",
        connector,
        "--region",
        region,
        "--project",
        project_id,
        "--format=json",
    ]


def _cloud_sql_command(project_id: str, instance: str) -> list[str]:
    return [
        "gcloud",
        "sql",
        "instances",
        "describe",
        instance,
        "--project",
        project_id,
        "--format=json",
    ]


def _redis_command(project_id: str, region: str, instance: str) -> list[str]:
    return [
        "gcloud",
        "redis",
        "instances",
        "describe",
        instance,
        "--region",
        region,
        "--project",
        project_id,
        "--format=json",
    ]


def _secret_versions_command(project_id: str, secret_name: str) -> list[str]:
    return [
        "gcloud",
        "secrets",
        "versions",
        "list",
        secret_name,
        "--project",
        project_id,
        "--format=json",
    ]


def _cloud_run_command(project_id: str, region: str, service_name: str) -> list[str]:
    return [
        "gcloud",
        "run",
        "services",
        "describe",
        service_name,
        "--region",
        region,
        "--project",
        project_id,
        "--format=json",
    ]


def _cloud_run_ready(payload: dict[str, Any]) -> bool:
    conditions = payload.get("status", {}).get("conditions", [])
    if not isinstance(conditions, list):
        return False
    return any(
        isinstance(condition, dict)
        and condition.get("type") == "Ready"
        and condition.get("status") == "True"
        for condition in conditions
    )


def _cloud_sql_instance_from_connection_name(connection_name: str) -> str:
    parts = connection_name.split(":")
    if len(parts) == 3:
        return parts[2]
    return ""


def _has_nonempty(payload: dict[str, Any], key: str) -> bool:
    return bool(str(payload.get(key, "")).strip())


def _looks_like_placeholder(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("REPLACE_WITH", "TODO", "CHANGE_ME"))


def _status_passed(status: str) -> bool:
    return status == "ok" or status.startswith("skipped:")


__all__ = [
    "GcpStagingReadinessResult",
    "READINESS_PHASES",
    "REQUIRED_OPERATOR_KEYS",
    "check_gcp_staging_readiness",
    "main",
]


if __name__ == "__main__":
    main()
