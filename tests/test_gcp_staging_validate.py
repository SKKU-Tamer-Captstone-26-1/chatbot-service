from pathlib import Path
from subprocess import CompletedProcess

import pytest

from chatbot_service.deployment.gcp_staging_validate import (
    run_staging_validation,
    validate_staging_env,
)


def _valid_values() -> dict[str, str]:
    return {
        "CHATBOT_VALIDATION_TARGET": "chatbot.example.com:443",
        "CHATBOT_VALIDATION_SECURE": "true",
        "CHATBOT_VALIDATION_USER_ID": "validation-user",
        "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer validation-token",
        "RECOMMENDATION_SERVICE_GRPC_ADDR": "recommendation:9090",
        "RECOMMENDATION_SERVICE_GRPC_TLS": "false",
        "CHATBOT_CACHE_BACKEND": "redis",
        "CHATBOT_CACHE_REDIS_URL": "redis://10.0.0.3:6379/0",
        "CHATBOT_STORE_CONVERSATIONS": "true",
        "CHATBOT_DB_DSN": "postgres://user:pass@/chatbot?host=/cloudsql/project:region:db",
        "CHATBOT_LLM_PROVIDER": "huggingface_tgi",
        "CHATBOT_LLM_ENDPOINT_URL": "https://llm.example.com/v1/chat/completions",
        "CHATBOT_LLM_MODEL": "staging-model",
        "CHATBOT_LLM_AUTH_MODE": "bearer_env",
        "CHATBOT_LLM_API_KEY_ENV": "HF_TOKEN",
        "HF_TOKEN": "hf_token",
    }


def test_validate_staging_env_rejects_placeholders():
    values = _valid_values()
    values["CHATBOT_LLM_MODEL"] = "REPLACE_WITH_MODEL"

    with pytest.raises(ValueError, match="CHATBOT_LLM_MODEL"):
        validate_staging_env(values)


def test_run_staging_validation_dry_run_does_not_expose_values_or_call_runner():
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, env: dict[str, str]) -> CompletedProcess[str]:
        calls.append(cmd)
        return CompletedProcess(cmd, 0, stdout="{}", stderr="")

    result = run_staging_validation(
        _valid_values(),
        mode="smoke",
        dry_run=True,
        runner=runner,
    )

    assert result.command == ["chatbot-validate", "smoke"]
    assert result.returncode is None
    assert result.stdout == ""
    assert result.stderr == ""
    assert "CHATBOT_VALIDATION_AUTHORIZATION" in result.env_keys
    assert "Bearer validation-token" not in str(result)
    assert calls == []


def test_run_staging_validation_passes_values_through_environment():
    captured_env: dict[str, str] = {}

    def runner(cmd: list[str], *, env: dict[str, str]) -> CompletedProcess[str]:
        captured_env.update(env)
        return CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")

    result = run_staging_validation(_valid_values(), mode="preflight", runner=runner)

    assert result.returncode == 0
    assert result.stdout == '{"ok": true}'
    assert captured_env["CHATBOT_VALIDATION_AUTHORIZATION"] == "Bearer validation-token"
    assert captured_env["HF_TOKEN"] == "hf_token"


def test_run_staging_validation_writes_output_file(tmp_path: Path):
    output_file = tmp_path / "validation" / "smoke.json"

    def runner(cmd: list[str], *, env: dict[str, str]) -> CompletedProcess[str]:
        return CompletedProcess(cmd, 0, stdout='{"smoke": {"passed": true}}', stderr="")

    result = run_staging_validation(
        _valid_values(),
        mode="smoke",
        output_file=output_file,
        runner=runner,
    )

    assert result.output_file == str(output_file)
    assert output_file.read_text(encoding="utf-8") == '{"smoke": {"passed": true}}'


def test_run_staging_validation_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unsupported validation mode"):
        run_staging_validation(_valid_values(), mode="unknown")
