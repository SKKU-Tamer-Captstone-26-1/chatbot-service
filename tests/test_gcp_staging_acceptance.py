import json
from pathlib import Path

from chatbot_service.deployment.gcp_staging_acceptance import check_staging_acceptance


def test_staging_acceptance_passes_with_complete_validation_outputs(tmp_path: Path):
    _write_validation_outputs(tmp_path)

    result = check_staging_acceptance(tmp_path, include_artifact_check=False)

    assert result.passed is True
    assert result.checks["preflight_passed"] == "ok"
    assert result.checks["smoke_passed"] == "ok"
    assert result.checks["load_passed"] == "ok"


def test_staging_acceptance_fails_when_output_file_missing(tmp_path: Path):
    _write_json(tmp_path / "preflight.json", _preflight_payload())

    result = check_staging_acceptance(tmp_path, include_artifact_check=False)

    assert result.passed is False
    assert result.checks["file:smoke.json"] == "failed: missing"
    assert result.checks["file:load.json"] == "failed: missing"


def test_staging_acceptance_fails_when_smoke_does_not_prove_conversation_and_feedback(
    tmp_path: Path,
):
    _write_validation_outputs(tmp_path)
    payload = _smoke_payload()
    payload["smoke"]["feedback_ok"] = False
    _write_json(tmp_path / "smoke.json", payload)

    result = check_staging_acceptance(tmp_path, include_artifact_check=False)

    assert result.passed is False
    assert "feedback_ok" in result.checks["smoke_passed"]


def test_staging_acceptance_fails_when_load_threshold_evaluation_failed(tmp_path: Path):
    _write_validation_outputs(tmp_path)
    payload = _load_payload()
    payload["evaluations"]["warm"]["passed"] = False
    _write_json(tmp_path / "load.json", payload)

    result = check_staging_acceptance(tmp_path, include_artifact_check=False)

    assert result.passed is False
    assert "warm" in result.checks["load_passed"]


def _write_validation_outputs(root: Path) -> None:
    _write_json(root / "preflight.json", _preflight_payload())
    _write_json(root / "smoke.json", _smoke_payload())
    _write_json(root / "load.json", _load_payload())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _preflight_payload() -> dict:
    return {"preflight": {"passed": True, "checks": {"runtime_config": "ok"}}}


def _smoke_payload() -> dict:
    return {
        "preflight": {"passed": True, "checks": {"runtime_config": "ok"}},
        "smoke": {
            "health_ok": True,
            "ask_ok": True,
            "conversation_ok": True,
            "feedback_ok": True,
            "conversation_id": "conversation_1",
            "message_id": "message_1",
            "errors": [],
        },
    }


def _load_payload() -> dict:
    return {
        "preflight": {"passed": True, "checks": {"runtime_config": "ok"}},
        "cold": {
            "name": "cold",
            "total": 500,
            "success": 500,
            "failed": 0,
            "latency": {"count": 500, "p50_ms": 100, "p95_ms": 800, "p99_ms": 1000, "max_ms": 1200},
            "errors": {},
        },
        "warm": {
            "name": "warm",
            "total": 500,
            "success": 500,
            "failed": 0,
            "latency": {"count": 500, "p50_ms": 90, "p95_ms": 700, "p99_ms": 900, "max_ms": 1100},
            "errors": {},
        },
        "service_metrics": {"status": "ok", "snapshot": {}},
        "evaluations": {
            "cold": {"passed": True, "failures": []},
            "warm": {"passed": True, "failures": []},
            "warmup": {"passed": True, "failures": []},
        },
    }
