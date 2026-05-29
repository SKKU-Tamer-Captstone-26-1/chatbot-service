from subprocess import CompletedProcess

import pytest

from chatbot_service.deployment.gcp_staging_deploy import (
    build_cloudbuild_submit_command,
    submit_cloudbuild,
)


def _valid_values() -> dict[str, str]:
    return {
        "PROJECT_ID": "test-project",
        "REGION": "asia-northeast3",
        "REPOSITORY": "ontheblock-chatbot",
        "SERVICE_NAME": "ai-chatbot-service-staging",
        "MIGRATION_JOB_NAME": "ai-chatbot-service-migrate-staging",
        "CHATBOT_STAGING_SERVICE_ACCOUNT": "chatbot@test-project.iam.gserviceaccount.com",
        "CLOUD_SQL_CONNECTION_NAME": "test-project:asia-northeast3:chatbot",
        "SERVERLESS_VPC_CONNECTOR": "chatbot-staging",
        "AUTH_SERVICE_URL": "https://auth.example.com",
        "RECOMMENDATION_SERVICE_URL": "https://recommendation.example.com:443",
        "CHATBOT_LLM_ENDPOINT_URL": "https://llm.example.com/v1/chat/completions",
        "CHATBOT_LLM_MODEL": "staging-chatbot",
        "DB_DSN_SECRET_VERSION": "1",
        "REDIS_URL_SECRET_VERSION": "2",
        "HF_TOKEN_SECRET_VERSION": "3",
    }


def test_build_cloudbuild_submit_command_maps_substitutions():
    command = build_cloudbuild_submit_command(_valid_values())
    joined = " ".join(command)

    assert command[:3] == ["gcloud", "builds", "submit"]
    assert "--project" in command
    assert "test-project" in command
    assert "--config" in command
    assert "deploy/gcp/cloudbuild.staging.yaml" in command
    assert "_REGION=asia-northeast3" in joined
    assert "_SERVICE_ACCOUNT=chatbot@test-project.iam.gserviceaccount.com" in joined
    assert "_RECOMMENDATION_SERVICE_URL=https://recommendation.example.com:443" in joined
    assert "_CHATBOT_LLM_MODEL=staging-chatbot" in joined
    assert "_DB_DSN_SECRET_VERSION=1" in joined


def test_build_cloudbuild_submit_command_rejects_placeholders():
    values = _valid_values()
    values["REPOSITORY"] = "REPLACE_WITH_REPOSITORY"

    with pytest.raises(ValueError, match="REPOSITORY"):
        build_cloudbuild_submit_command(values)


def test_build_cloudbuild_submit_command_rejects_latest_secret_version():
    values = _valid_values()
    values["HF_TOKEN_SECRET_VERSION"] = "latest"

    with pytest.raises(ValueError, match="HF_TOKEN_SECRET_VERSION"):
        build_cloudbuild_submit_command(values)


def test_submit_cloudbuild_dry_run_does_not_call_runner():
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> CompletedProcess[bytes]:
        calls.append(cmd)
        return CompletedProcess(cmd, 0)

    result = submit_cloudbuild(_valid_values(), dry_run=True, runner=runner)

    assert result.dry_run is True
    assert result.submitted is False
    assert result.command
    assert calls == []


def test_submit_cloudbuild_calls_runner_when_not_dry_run():
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> CompletedProcess[bytes]:
        calls.append(cmd)
        return CompletedProcess(cmd, 0)

    result = submit_cloudbuild(_valid_values(), runner=runner)

    assert result.submitted is True
    assert calls == [result.command]
