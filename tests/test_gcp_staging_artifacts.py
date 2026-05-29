from pathlib import Path

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


def test_gcp_staging_runbook_records_required_acceptance_gates():
    runbook = (ROOT / "docs/deployment/gcp-staging.md").read_text(encoding="utf-8")

    assert "chatbot-validate preflight" in runbook
    assert "chatbot-validate smoke" in runbook
    assert "chatbot-validate load" in runbook
    assert "chatbot-migrate" in runbook
    assert "--use-http2" in runbook
