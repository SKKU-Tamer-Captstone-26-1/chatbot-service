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


def test_cloudbuild_pipeline_runs_migrations_before_service_deploy():
    pipeline = (ROOT / "deploy/gcp/cloudbuild.staging.yaml").read_text(encoding="utf-8")

    migration_index = pipeline.index('id: "run-migrations"')
    deploy_index = pipeline.index('id: "deploy-service"')
    assert migration_index < deploy_index
    assert "gcloud" in pipeline
    assert "jobs" in pipeline
    assert "deploy" in pipeline
    assert "--command=chatbot-migrate" in pipeline
    assert "--execute-now" in pipeline
    assert "--wait" in pipeline
    assert "--env-vars-file=deploy/gcp/staging.env.yaml" in pipeline
    assert "--set-secrets=" in pipeline
    assert "--use-http2" in pipeline
    assert ":latest" not in pipeline


def test_validation_env_example_has_required_staging_knobs_as_placeholders():
    template = (ROOT / "deploy/gcp/staging.validation.env.example").read_text(
        encoding="utf-8"
    )

    assert "CHATBOT_VALIDATION_TARGET=REPLACE_WITH_STAGING_GATEWAY_HOST:443" in template
    assert (
        'CHATBOT_VALIDATION_AUTHORIZATION="Bearer REPLACE_WITH_STAGING_TOKEN"'
        in template
    )
    assert "CHATBOT_VALIDATION_CONCURRENCY=500" in template
    assert "CHATBOT_VALIDATION_REQUESTS=500" in template
    assert "CHATBOT_CACHE_BACKEND=redis" in template
    assert "CHATBOT_LLM_PROVIDER=huggingface_tgi" in template
    assert "HF_TOKEN=REPLACE_WITH_OPERATOR_LOCAL_TOKEN" in template


def test_gitignore_blocks_filled_operator_validation_env():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "deploy/gcp/staging.validation.env" in gitignore


def test_gcp_staging_runbook_records_required_acceptance_gates():
    runbook = (ROOT / "docs/deployment/gcp-staging.md").read_text(encoding="utf-8")

    assert "deploy/gcp/cloudbuild.staging.yaml" in runbook
    assert "deploy/gcp/staging.validation.env.example" in runbook
    assert "chatbot-validate preflight" in runbook
    assert "chatbot-validate smoke" in runbook
    assert "chatbot-validate load" in runbook
    assert "chatbot-migrate" in runbook
    assert "--use-http2" in runbook
