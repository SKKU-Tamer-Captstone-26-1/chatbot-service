import pytest

from chatbot_service.metrics import MetricsRecorder
from chatbot_service.server import load_generated_chatbot_grpc
from chatbot_service.validation.cli import main as validation_main
from chatbot_service.validation.client import (
    _assert_grounded_response,
    _beverage_request,
    _load_request,
    _venue_request,
)
from chatbot_service.validation.config import load_validation_config
from chatbot_service.validation.preflight import run_preflight_checks
from chatbot_service.validation.service_metrics import read_service_metrics
from chatbot_service.validation.summary import (
    evaluate_thresholds,
    evaluate_warmup_improvement,
    summarize_latencies,
    summarize_run,
)


def test_validation_config_parses_target_metadata_and_load_settings():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_TARGET": "https://chatbot.example.com",
            "CHATBOT_VALIDATION_USER_ID": "user_123",
            "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer token",
            "CHATBOT_VALIDATION_CONCURRENCY": "250",
            "CHATBOT_VALIDATION_REQUESTS": "750",
            "CHATBOT_VALIDATION_P95_THRESHOLD_MS": "1200",
            "CHATBOT_VALIDATION_CACHE_WARMUP_MIN_IMPROVEMENT_RATIO": "0.10",
            "RECOMMENDATION_SERVICE_GRPC_ADDR": "recommendation.example.com:443",
            "RECOMMENDATION_SERVICE_GRPC_TLS": "true",
            "CHATBOT_STORE_CONVERSATIONS": "true",
            "CHATBOT_DB_DSN": "postgres://chatbot:pass@localhost:5432/chatbot",
            "CHATBOT_CACHE_BACKEND": "redis",
            "CHATBOT_CACHE_REDIS_URL": "redis://localhost:6379/0",
            "CHATBOT_LLM_PROVIDER": "huggingface_tgi",
            "CHATBOT_LLM_ENDPOINT_URL": "https://llm.example.com/v1/chat/completions",
            "CHATBOT_LLM_MODEL": "ontheblock-chatbot",
            "CHATBOT_LLM_AUTH_MODE": "bearer_env",
            "CHATBOT_LLM_API_KEY_ENV": "HF_TOKEN",
            "HF_TOKEN": "secret",
            "CHATBOT_VALIDATION_SERVICE_METRICS_PATH": "/tmp/chatbot-metrics.json",
        }
    )

    assert config.target == "chatbot.example.com"
    assert config.secure is True
    assert config.metadata == [
        ("x-user-id", "user_123"),
        ("authorization", "Bearer token"),
    ]
    assert config.concurrency == 250
    assert config.requests == 750
    assert config.p95_threshold_ms == 1200
    assert config.cache_warmup_min_improvement_ratio == 0.10
    assert config.cache_backend == "redis"
    assert config.cache_redis_url == "redis://localhost:6379/0"
    assert config.require_redis_preflight is True
    assert config.require_runtime_preflight is True
    assert config.require_authorization is True
    assert config.recommendation_service_url == "recommendation.example.com:443"
    assert config.recommendation_service_grpc_tls is True
    assert config.store_conversations is True
    assert config.db_dsn == "postgres://chatbot:pass@localhost:5432/chatbot"
    assert config.llm_provider == "huggingface_tgi"
    assert config.llm_endpoint_url == "https://llm.example.com/v1/chat/completions"
    assert config.llm_model == "ontheblock-chatbot"
    assert config.llm_auth_mode == "bearer_env"
    assert config.llm_api_key_env == "HF_TOKEN"
    assert config.llm_api_key_available is True
    assert config.service_metrics_path == "/tmp/chatbot-metrics.json"


def test_validation_config_allows_insecure_override_for_tls_terminated_proxy():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_TARGET": "https://chatbot.example.com",
            "CHATBOT_VALIDATION_SECURE": "false",
        }
    )

    assert config.target == "chatbot.example.com"
    assert config.secure is False


def test_validation_cli_preflight_prints_result_and_exits_success(monkeypatch, capsys):
    monkeypatch.setenv("CHATBOT_VALIDATION_AUTHORIZATION", "Bearer token")
    monkeypatch.setenv("CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT", "false")
    monkeypatch.setenv("RECOMMENDATION_SERVICE_GRPC_ADDR", "recommendation:9090")
    monkeypatch.setenv("CHATBOT_STORE_CONVERSATIONS", "false")
    monkeypatch.setenv("CHATBOT_CACHE_BACKEND", "memory")
    monkeypatch.setenv("CHATBOT_LLM_PROVIDER", "huggingface_tgi")
    monkeypatch.setenv("CHATBOT_LLM_ENDPOINT_URL", "http://localhost:8000/v1/chat/completions")
    monkeypatch.setenv("CHATBOT_LLM_MODEL", "local-chatbot")
    monkeypatch.setenv("CHATBOT_LLM_AUTH_MODE", "none")

    validation_main(["preflight"])

    assert '"passed": true' in capsys.readouterr().out


def test_latency_summary_and_threshold_evaluation():
    latencies = [10, 20, 30, 40, 100]
    summary = summarize_run("cold", latencies, ["UNAVAILABLE", "UNAVAILABLE"])

    assert summarize_latencies(latencies).p95_ms == 100
    assert summary.total == 7
    assert summary.success == 5
    assert summary.failed == 2
    assert summary.errors == {"UNAVAILABLE": 2}
    failed = evaluate_thresholds(summary, p95_threshold_ms=50)
    assert failed.passed is False
    assert "2 requests failed" in failed.failures
    assert "p95 latency" in failed.failures[1]


def test_warmup_improvement_can_be_disabled_or_enforced():
    cold = summarize_run("cold", [100, 100, 100], [])
    warm = summarize_run("warm", [95, 95, 95], [])

    assert evaluate_warmup_improvement(
        cold,
        warm,
        min_improvement_ratio=-1,
    ).passed
    assert evaluate_warmup_improvement(
        cold,
        warm,
        min_improvement_ratio=0.10,
    ).passed is False


def test_validation_requests_use_expected_contract_fields():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    config = load_validation_config({})

    beverage = _beverage_request(pb2, config)
    venue = _venue_request(pb2, config, index=2)
    mixed = _load_request(pb2, config, index=3)

    assert beverage.message == "내 취향에 맞는 술 추천해줘"
    assert beverage.screen_context == pb2.SCREEN_CONTEXT_HOME
    assert beverage.budget_mode == pb2.BUDGET_MODE_SOFT
    assert venue.selected_beverage_id == "bev_1"
    assert venue.screen_context == pb2.SCREEN_CONTEXT_MAP
    assert venue.HasField("lat")
    assert mixed.selected_beverage_id == "bev_1"


def test_grounded_response_validation_accepts_safe_response_shapes():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2

    answered = pb2.AskChatbotResponse(
        status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
        answer="답변",
        cards=[
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="테스트 위스키",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=1,
                    result_id="bev_result_1",
                    beverage_id="bev_1",
                    name_ko="테스트 위스키",
                ),
            )
        ],
    )
    answered.used_sources.beverage_result_ids.append("bev_result_1")
    insufficient = pb2.AskChatbotResponse(
        status=pb2.CHATBOT_RESPONSE_STATUS_INSUFFICIENT_DATA,
        answer="위치 정보가 필요해요.",
        missing_facts=["detailed_location"],
    )

    _assert_grounded_response(answered, pb2)
    _assert_grounded_response(insufficient, pb2)


def test_grounded_response_validation_rejects_unsupported_success_shape():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2

    with pytest.raises(ValueError, match="no cards"):
        _assert_grounded_response(
            pb2.AskChatbotResponse(
                status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
                answer="답변",
            ),
            pb2,
        )


def test_grounded_response_validation_rejects_source_mismatch_and_rank_reorder():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    mismatch = pb2.AskChatbotResponse(
        status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
        answer="답변",
        cards=[
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="테스트 위스키",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=1,
                    result_id="bev_result_1",
                ),
            )
        ],
    )
    mismatch.used_sources.beverage_result_ids.append("other_result")

    with pytest.raises(ValueError, match="used_sources"):
        _assert_grounded_response(mismatch, pb2)

    reordered = pb2.AskChatbotResponse(
        status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
        answer="답변",
        cards=[
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="두번째",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=2,
                    result_id="bev_result_2",
                ),
            ),
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="첫번째",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=1,
                    result_id="bev_result_1",
                ),
            ),
        ],
    )
    reordered.used_sources.beverage_result_ids.extend(["bev_result_2", "bev_result_1"])

    with pytest.raises(ValueError, match="ranks"):
        _assert_grounded_response(reordered, pb2)


def test_grounded_response_validation_accepts_mixed_card_rank_sequences():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    response = pb2.AskChatbotResponse(
        status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
        answer="답변",
        cards=[
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="음료",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=1,
                    result_id="bev_result_1",
                ),
            ),
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION,
                title="장소",
                venue_recommendation=pb2.VenueRecommendationCard(
                    rank=1,
                    result_id="venue_result_1",
                ),
            ),
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_COMPARISON,
                title="비교",
                comparison=pb2.ComparisonCard(
                    options=[
                        pb2.PurchaseOptionCard(result_id="venue_result_1"),
                    ],
                ),
            ),
        ],
    )
    response.used_sources.beverage_result_ids.append("bev_result_1")
    response.used_sources.venue_result_ids.append("venue_result_1")

    _assert_grounded_response(response, pb2)


@pytest.mark.anyio
async def test_preflight_skips_redis_when_not_required():
    config = load_validation_config(
        {
            "CHATBOT_CACHE_BACKEND": "memory",
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT": "false",
            "CHATBOT_VALIDATION_REQUIRE_RUNTIME_PREFLIGHT": "false",
            "CHATBOT_VALIDATION_REQUIRE_AUTHORIZATION": "false",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is True
    assert result.checks["runtime_config"] == "skipped"
    assert result.checks["validation_authorization"] == "skipped"
    assert result.checks["redis"] == "skipped"


@pytest.mark.anyio
async def test_preflight_fails_when_redis_required_without_url():
    config = load_validation_config(
        {
            "CHATBOT_CACHE_BACKEND": "redis",
            "CHATBOT_CACHE_REDIS_URL": "",
            "CHATBOT_VALIDATION_REQUIRE_RUNTIME_PREFLIGHT": "false",
            "CHATBOT_VALIDATION_REQUIRE_AUTHORIZATION": "false",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is False
    assert result.checks["redis"] == "failed: CHATBOT_CACHE_REDIS_URL is required"


@pytest.mark.anyio
async def test_preflight_fails_fast_for_missing_runtime_settings():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer token",
            "CHATBOT_CACHE_BACKEND": "memory",
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT": "false",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is False
    assert result.checks["recommendation_service_grpc_addr"] == (
        "failed: RECOMMENDATION_SERVICE_GRPC_ADDR is required"
    )
    assert result.checks["postgres_dsn"] == "failed: CHATBOT_DB_DSN is required"
    assert result.checks["llm_provider"] == "failed: CHATBOT_LLM_PROVIDER is required for staging"


@pytest.mark.anyio
async def test_preflight_allows_local_llm_without_api_key_when_auth_none():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer token",
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT": "false",
            "RECOMMENDATION_SERVICE_GRPC_ADDR": "recommendation:9090",
            "CHATBOT_STORE_CONVERSATIONS": "false",
            "CHATBOT_CACHE_BACKEND": "memory",
            "CHATBOT_LLM_PROVIDER": "huggingface_tgi",
            "CHATBOT_LLM_ENDPOINT_URL": "http://localhost:8000/v1/chat/completions",
            "CHATBOT_LLM_MODEL": "local-chatbot",
            "CHATBOT_LLM_AUTH_MODE": "none",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is True
    assert result.checks["postgres_dsn"] == "skipped"
    assert result.checks["llm_api_key"] == "skipped"
    assert result.checks["llm_endpoint_format"] == "ok"


@pytest.mark.anyio
async def test_preflight_rejects_invalid_llm_endpoint_path():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer token",
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT": "false",
            "RECOMMENDATION_SERVICE_GRPC_ADDR": "recommendation:9090",
            "CHATBOT_STORE_CONVERSATIONS": "false",
            "CHATBOT_CACHE_BACKEND": "memory",
            "CHATBOT_LLM_PROVIDER": "huggingface_tgi",
            "CHATBOT_LLM_ENDPOINT_URL": "https://llm.example.com/v1/completions",
            "CHATBOT_LLM_MODEL": "bad-endpoint-chatbot",
            "CHATBOT_LLM_AUTH_MODE": "none",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is False
    assert (
        result.checks["llm_endpoint_format"]
        == "failed: CHATBOT_LLM_ENDPOINT_URL must end with /v1/chat/completions"
    )


@pytest.mark.anyio
async def test_preflight_requires_api_key_when_llm_auth_mode_is_bearer_env():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer token",
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT": "false",
            "RECOMMENDATION_SERVICE_GRPC_ADDR": "recommendation:9090",
            "CHATBOT_STORE_CONVERSATIONS": "false",
            "CHATBOT_CACHE_BACKEND": "memory",
            "CHATBOT_LLM_PROVIDER": "huggingface_tgi",
            "CHATBOT_LLM_ENDPOINT_URL": "https://llm.example.com/v1/chat/completions",
            "CHATBOT_LLM_MODEL": "remote-chatbot",
            "CHATBOT_LLM_AUTH_MODE": "bearer_env",
            "CHATBOT_LLM_API_KEY_ENV": "HF_TOKEN",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is False
    assert result.checks["llm_api_key"] == "failed: HF_TOKEN is required"


@pytest.mark.anyio
async def test_preflight_rejects_placeholder_values():
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_AUTHORIZATION": "Bearer REPLACE_WITH_TEST_TOKEN",
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT": "false",
            "RECOMMENDATION_SERVICE_GRPC_ADDR": "REPLACE_WITH_RECOMMENDATION_GRPC_ADDR",
            "CHATBOT_STORE_CONVERSATIONS": "false",
            "CHATBOT_CACHE_BACKEND": "memory",
            "CHATBOT_LLM_PROVIDER": "huggingface_tgi",
            "CHATBOT_LLM_ENDPOINT_URL": "https://REPLACE_WITH_HF_ENDPOINT/v1/chat/completions",
            "CHATBOT_LLM_MODEL": "REPLACE_ME",
            "CHATBOT_LLM_AUTH_MODE": "none",
        }
    )

    result = await run_preflight_checks(config)

    assert result.passed is False
    assert result.checks["validation_authorization"] == (
        "failed: CHATBOT_VALIDATION_AUTHORIZATION still has a placeholder value"
    )
    assert result.checks["recommendation_service_grpc_addr"] == (
        "failed: RECOMMENDATION_SERVICE_GRPC_ADDR still has a placeholder value"
    )
    assert result.checks["llm_endpoint_url"] == (
        "failed: CHATBOT_LLM_ENDPOINT_URL still has a placeholder value"
    )
    assert result.checks["llm_model"] == "failed: CHATBOT_LLM_MODEL still has a placeholder value"


def test_metrics_snapshot_file_can_be_read_by_validation(tmp_path):
    path = tmp_path / "metrics.json"
    recorder = MetricsRecorder(snapshot_path=path)
    recorder.increment("recommendation.cache_hit", operation="beverage_recommendations")
    recorder.observe("llm.call", 0.125)

    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_SERVICE_METRICS_PATH": str(path),
        }
    )
    metrics = read_service_metrics(config)

    assert metrics["status"] == "ok"
    snapshot = metrics["snapshot"]
    assert snapshot["counters"][
        "recommendation.cache_hit|operation=beverage_recommendations"
    ] == 1
    assert snapshot["timers"]["llm.call"]["p95"] == 0.125


def test_service_metrics_reader_reports_missing_file(tmp_path):
    config = load_validation_config(
        {
            "CHATBOT_VALIDATION_SERVICE_METRICS_PATH": str(tmp_path / "missing.json"),
        }
    )

    metrics = read_service_metrics(config)

    assert metrics["status"] == "missing"
