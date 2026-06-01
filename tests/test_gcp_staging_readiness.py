import json
from subprocess import CompletedProcess

from chatbot_service.deployment.gcp_staging_readiness import check_gcp_staging_readiness


def _values() -> dict[str, str]:
    return {
        "PROJECT_ID": "test-project",
        "REGION": "asia-northeast3",
        "REPOSITORY": "ontheblock-chatbot",
        "SERVICE_NAME": "ai-chatbot-service-staging",
        "MIGRATION_JOB_NAME": "ai-chatbot-service-migrate-staging",
        "CHATBOT_STAGING_SERVICE_ACCOUNT": "chatbot@test-project.iam.gserviceaccount.com",
        "CLOUD_SQL_CONNECTION_NAME": "test-project:asia-northeast3:chatbot-postgres",
        "SERVERLESS_VPC_CONNECTOR": "chatbot-staging",
        "AUTH_SERVICE_URL": "https://auth.example.com",
        "RECOMMENDATION_SERVICE_GRPC_ADDR": "recommendation.example.com:443",
        "RECOMMENDATION_SERVICE_GRPC_TLS": "true",
        "CHATBOT_LLM_ENDPOINT_URL": "https://llm.example.com/v1/chat/completions",
        "CHATBOT_LLM_MODEL": "staging-chatbot",
        "DB_DSN_SECRET_VERSION": "1",
        "REDIS_URL_SECRET_VERSION": "2",
        "HF_TOKEN_SECRET_VERSION": "3",
    }


def test_gcp_staging_readiness_passes_for_predeploy_resources():
    result = check_gcp_staging_readiness(_values(), runner=_runner())

    assert result.passed is True
    assert result.checks["artifact_registry"] == "ok"
    assert result.checks["cloud_sql_instance"] == "ok"
    assert result.checks["redis_instance"] == "ok"
    assert result.checks["secret_version:chatbot-staging-db-dsn"] == "ok"
    assert result.checks["cloud_run_service"] == "skipped: predeploy"


def test_gcp_staging_readiness_checks_cloud_run_in_postdeploy_phase():
    result = check_gcp_staging_readiness(_values(), phase="postdeploy", runner=_runner())

    assert result.passed is True
    assert result.checks["cloud_run_service"] == "ok"


def test_gcp_staging_readiness_fails_on_placeholders_before_running_gcloud():
    values = _values()
    values["CHATBOT_LLM_MODEL"] = "REPLACE_WITH_MODEL"

    result = check_gcp_staging_readiness(values, runner=_runner())

    assert result.passed is False
    assert result.checks["operator_env:CHATBOT_LLM_MODEL"] == "failed: placeholder"


def test_gcp_staging_readiness_fails_when_secret_version_is_not_enabled():
    values = _values()
    values["HF_TOKEN_SECRET_VERSION"] = "9"

    result = check_gcp_staging_readiness(values, runner=_runner())

    assert result.passed is False
    assert (
        result.checks["secret_version:chatbot-staging-hf-token"]
        == "failed: version 9 is not enabled"
    )


def test_gcp_staging_readiness_fails_when_cloud_run_missing_postdeploy():
    result = check_gcp_staging_readiness(
        _values(),
        phase="postdeploy",
        runner=_runner(missing_cloud_run=True),
    )

    assert result.passed is False
    assert result.checks["cloud_run_service"] == "failed: command returned 1"


def _runner(*, missing_cloud_run: bool = False):
    def run(cmd: list[str]) -> CompletedProcess[str]:
        command = " ".join(cmd)
        if "artifacts repositories describe" in command:
            return _json(cmd, {"name": "projects/test/locations/asia/repositories/ontheblock"})
        if "iam service-accounts describe" in command:
            return _json(cmd, {"email": "chatbot@test-project.iam.gserviceaccount.com"})
        if "vpc-access connectors describe" in command:
            return _json(cmd, {"state": "READY"})
        if "sql instances describe" in command:
            return _json(
                cmd,
                {
                    "connectionName": "test-project:asia-northeast3:chatbot-postgres",
                    "state": "RUNNABLE",
                },
            )
        if "redis instances describe" in command:
            return _json(cmd, {"host": "10.0.0.2", "port": 6379, "state": "READY"})
        if "secrets versions list chatbot-staging-db-dsn" in command:
            return _json(cmd, [_secret_version("1")])
        if "secrets versions list chatbot-staging-redis-url" in command:
            return _json(cmd, [_secret_version("2")])
        if "secrets versions list chatbot-staging-hf-token" in command:
            return _json(cmd, [_secret_version("3")])
        if "run services describe" in command:
            if missing_cloud_run:
                return CompletedProcess(cmd, 1, "", "missing")
            return _json(
                cmd,
                {"status": {"conditions": [{"type": "Ready", "status": "True"}]}},
            )
        return CompletedProcess(cmd, 1, "", "unknown command")

    return run


def _json(cmd: list[str], payload: object) -> CompletedProcess[str]:
    return CompletedProcess(cmd, 0, json.dumps(payload), "")


def _secret_version(version: str) -> dict[str, str]:
    return {
        "name": f"projects/test/secrets/secret/versions/{version}",
        "state": "ENABLED",
    }
