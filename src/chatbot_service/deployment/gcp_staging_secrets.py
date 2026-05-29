from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

SECRET_ENV_TO_MANAGER_NAME = {
    "CHATBOT_DB_DSN": "chatbot-staging-db-dsn",
    "CHATBOT_CACHE_REDIS_URL": "chatbot-staging-redis-url",
    "HF_TOKEN": "chatbot-staging-hf-token",
    "CHATBOT_VALIDATION_AUTHORIZATION": "chatbot-staging-validation-authorization",
}


class CommandRunner(Protocol):
    def __call__(self, cmd: list[str], *, input: bytes) -> subprocess.CompletedProcess[bytes]: ...


@dataclass(frozen=True)
class SecretVersionPlan:
    env_key: str
    secret_name: str
    command: list[str]


@dataclass(frozen=True)
class SecretVersionResult:
    project_id: str
    dry_run: bool
    uploaded: list[str]
    commands: list[list[str]]


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=value")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{path}:{line_number}: empty key")
        values[key] = _parse_value(raw_value.strip(), path=path, line_number=line_number)
    return values


def build_secret_version_plan(
    values: dict[str, str],
    *,
    allow_placeholders: bool = False,
) -> tuple[str, list[SecretVersionPlan]]:
    project_id = _required(values, "PROJECT_ID", allow_placeholders=allow_placeholders)
    plans: list[SecretVersionPlan] = []
    for env_key, secret_name in SECRET_ENV_TO_MANAGER_NAME.items():
        secret_value = _required(values, env_key, allow_placeholders=allow_placeholders)
        command = [
            "gcloud",
            "secrets",
            "versions",
            "add",
            secret_name,
            "--project",
            project_id,
            "--data-file=-",
        ]
        _assert_secret_not_in_command(command, secret_value, env_key)
        plans.append(SecretVersionPlan(env_key=env_key, secret_name=secret_name, command=command))
    return project_id, plans


def upload_secret_versions(
    values: dict[str, str],
    *,
    dry_run: bool = False,
    allow_placeholders: bool = False,
    runner: CommandRunner | None = None,
) -> SecretVersionResult:
    project_id, plans = build_secret_version_plan(
        values,
        allow_placeholders=allow_placeholders,
    )
    runner = runner or _run_gcloud
    uploaded: list[str] = []
    commands: list[list[str]] = []
    for plan in plans:
        commands.append(plan.command)
        if dry_run:
            continue
        runner(plan.command, input=values[plan.env_key].encode("utf-8"))
        uploaded.append(plan.secret_name)
    return SecretVersionResult(
        project_id=project_id,
        dry_run=dry_run,
        uploaded=uploaded,
        commands=commands,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Upload GCP staging Secret Manager versions")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("deploy/gcp/staging.secrets.env"),
        help="Ignored operator-local env file containing staging secret values.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print planned secret version commands without uploading values.",
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow REPLACE_WITH placeholders. Intended only for checking templates.",
    )
    args = parser.parse_args(argv)

    values = load_env_file(args.env_file)
    result = upload_secret_versions(
        values,
        dry_run=args.dry_run,
        allow_placeholders=args.allow_placeholders,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


def _parse_value(raw_value: str, *, path: Path, line_number: int) -> str:
    if not raw_value:
        return ""
    try:
        parts = shlex.split(raw_value, comments=False, posix=True)
    except ValueError as exc:
        raise ValueError(f"{path}:{line_number}: invalid shell value: {exc}") from exc
    if len(parts) != 1:
        raise ValueError(f"{path}:{line_number}: expected a single value")
    return parts[0]


def _required(values: dict[str, str], key: str, *, allow_placeholders: bool) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    if not allow_placeholders and _looks_like_placeholder(value):
        raise ValueError(f"{key} still has a placeholder value")
    return value


def _looks_like_placeholder(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("REPLACE_WITH", "TODO", "CHANGE_ME"))


def _assert_secret_not_in_command(command: list[str], secret_value: str, env_key: str) -> None:
    if secret_value and any(secret_value in part for part in command):
        raise ValueError(f"{env_key} secret value leaked into gcloud command arguments")


def _run_gcloud(cmd: list[str], *, input: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, input=input, check=True)


__all__ = [
    "SECRET_ENV_TO_MANAGER_NAME",
    "SecretVersionPlan",
    "SecretVersionResult",
    "build_secret_version_plan",
    "load_env_file",
    "main",
    "upload_secret_versions",
]


if __name__ == "__main__":
    main()
