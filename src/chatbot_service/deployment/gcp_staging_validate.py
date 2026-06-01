from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from chatbot_service.deployment.gcp_staging_secrets import load_env_file


class CommandRunner(Protocol):
    def __call__(
        self,
        cmd: list[str],
        *,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class ValidationCommandResult:
    mode: str
    dry_run: bool
    command: list[str]
    env_keys: list[str]
    output_file: str
    returncode: int | None
    stdout: str
    stderr: str


REQUIRED_VALIDATION_ENV_KEYS = (
    "CHATBOT_VALIDATION_TARGET",
    "CHATBOT_VALIDATION_SECURE",
    "CHATBOT_VALIDATION_USER_ID",
    "CHATBOT_VALIDATION_AUTHORIZATION",
    "RECOMMENDATION_SERVICE_GRPC_ADDR",
    "RECOMMENDATION_SERVICE_GRPC_TLS",
    "CHATBOT_CACHE_BACKEND",
    "CHATBOT_CACHE_REDIS_URL",
    "CHATBOT_STORE_CONVERSATIONS",
    "CHATBOT_DB_DSN",
    "CHATBOT_LLM_PROVIDER",
    "CHATBOT_LLM_ENDPOINT_URL",
    "CHATBOT_LLM_MODEL",
    "CHATBOT_LLM_AUTH_MODE",
)

VALIDATION_MODES = ("preflight", "smoke", "load")


def validate_staging_env(
    values: dict[str, str],
    *,
    allow_placeholders: bool = False,
) -> None:
    for key in REQUIRED_VALIDATION_ENV_KEYS:
        value = values.get(key, "").strip()
        if not value:
            raise ValueError(f"{key} is required")
        if not allow_placeholders and _looks_like_placeholder(value):
            raise ValueError(f"{key} still has a placeholder value")


def run_staging_validation(
    values: dict[str, str],
    *,
    mode: str,
    dry_run: bool = False,
    allow_placeholders: bool = False,
    output_file: Path | None = None,
    runner: CommandRunner | None = None,
) -> ValidationCommandResult:
    if mode not in VALIDATION_MODES:
        raise ValueError(f"unsupported validation mode: {mode}")
    validate_staging_env(values, allow_placeholders=allow_placeholders)
    command = ["chatbot-validate", mode]
    env = {**os.environ, **values}
    env_keys = sorted(values)

    if dry_run:
        return ValidationCommandResult(
            mode=mode,
            dry_run=True,
            command=command,
            env_keys=env_keys,
            output_file=str(output_file or ""),
            returncode=None,
            stdout="",
            stderr="",
        )

    runner = runner or _run_validation
    completed = runner(command, env=env)
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(completed.stdout, encoding="utf-8")
    return ValidationCommandResult(
        mode=mode,
        dry_run=False,
        command=command,
        env_keys=env_keys,
        output_file=str(output_file or ""),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run GCP staging validation from an env file")
    parser.add_argument("mode", choices=VALIDATION_MODES)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("deploy/gcp/staging.validation.env"),
        help="Ignored operator-local env file containing staging validation settings.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Optional ignored file to store chatbot-validate JSON output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate env file and print planned command without running validation.",
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow REPLACE_WITH placeholders. Intended only for checking templates.",
    )
    args = parser.parse_args(argv)

    values = load_env_file(args.env_file)
    result = run_staging_validation(
        values,
        mode=args.mode,
        dry_run=args.dry_run,
        allow_placeholders=args.allow_placeholders,
        output_file=args.output_file,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if result.returncode not in {None, 0}:
        raise SystemExit(result.returncode)


def _looks_like_placeholder(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("REPLACE_WITH", "TODO", "CHANGE_ME"))


def _run_validation(
    cmd: list[str],
    *,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)


__all__ = [
    "REQUIRED_VALIDATION_ENV_KEYS",
    "VALIDATION_MODES",
    "ValidationCommandResult",
    "main",
    "run_staging_validation",
    "validate_staging_env",
]


if __name__ == "__main__":
    main()
