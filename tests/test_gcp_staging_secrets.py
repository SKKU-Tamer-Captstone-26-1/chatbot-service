from pathlib import Path
from subprocess import CompletedProcess

import pytest

from chatbot_service.deployment.gcp_staging_secrets import (
    SECRET_ENV_TO_MANAGER_NAME,
    build_secret_version_plan,
    load_env_file,
    upload_secret_versions,
)


def _valid_values() -> dict[str, str]:
    return {
        "PROJECT_ID": "test-project",
        "CHATBOT_DB_DSN": "postgres://user:pass@/chatbot?host=/cloudsql/project:region:db",
        "CHATBOT_CACHE_REDIS_URL": "redis://10.0.0.3:6379/0",
        "HF_TOKEN": "hf_test_token",
        "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer validation-token",
    }


def test_load_env_file_parses_quoted_values(tmp_path: Path):
    env_file = tmp_path / "staging.secrets.env"
    env_file.write_text(
        "\n".join(
            [
                "PROJECT_ID=test-project",
                'CHATBOT_VALIDATION_AUTHORIZATION="Bearer validation-token"',
            ]
        ),
        encoding="utf-8",
    )

    values = load_env_file(env_file)

    assert values["PROJECT_ID"] == "test-project"
    assert values["CHATBOT_VALIDATION_AUTHORIZATION"] == "Bearer validation-token"


def test_build_secret_version_plan_rejects_placeholders():
    values = _valid_values()
    values["HF_TOKEN"] = "REPLACE_WITH_TOKEN"

    with pytest.raises(ValueError, match="HF_TOKEN"):
        build_secret_version_plan(values)


def test_build_secret_version_plan_keeps_secret_values_out_of_command_args():
    values = _valid_values()

    project_id, plans = build_secret_version_plan(values)
    commands = [" ".join(plan.command) for plan in plans]

    assert project_id == "test-project"
    assert len(plans) == len(SECRET_ENV_TO_MANAGER_NAME)
    assert all("--data-file=-" in command for command in commands)
    assert all("hf_test_token" not in command for command in commands)
    assert all("validation-token" not in command for command in commands)


def test_upload_secret_versions_dry_run_does_not_call_runner():
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, input: bytes) -> CompletedProcess[bytes]:
        calls.append(cmd)
        return CompletedProcess(cmd, 0)

    result = upload_secret_versions(_valid_values(), dry_run=True, runner=runner)

    assert result.dry_run is True
    assert result.uploaded == []
    assert calls == []
    assert result.commands


def test_upload_secret_versions_passes_secret_values_through_stdin():
    captured: dict[str, bytes] = {}

    def runner(cmd: list[str], *, input: bytes) -> CompletedProcess[bytes]:
        captured[cmd[4]] = input
        return CompletedProcess(cmd, 0)

    result = upload_secret_versions(_valid_values(), runner=runner)

    assert set(result.uploaded) == set(SECRET_ENV_TO_MANAGER_NAME.values())
    assert captured["chatbot-staging-hf-token"] == b"hf_test_token"
    assert captured["chatbot-staging-validation-authorization"] == b"Bearer validation-token"
