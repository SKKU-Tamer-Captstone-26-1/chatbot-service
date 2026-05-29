from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from chatbot_service.deployment.gcp_staging_check import check_gcp_staging_artifacts


@dataclass(frozen=True)
class StagingAcceptanceResult:
    passed: bool
    checks: dict[str, str]


VALIDATION_OUTPUT_FILES = {
    "preflight": "preflight.json",
    "smoke": "smoke.json",
    "load": "load.json",
}


def check_staging_acceptance(
    validation_output_dir: Path = Path("deploy/gcp/validation-output"),
    *,
    root: Path | None = None,
    include_artifact_check: bool = True,
) -> StagingAcceptanceResult:
    checks: dict[str, str] = {}
    payloads: dict[str, dict[str, Any]] = {}

    if include_artifact_check:
        artifact_result = check_gcp_staging_artifacts(root)
        checks["artifact_preflight"] = "ok" if artifact_result.passed else "failed"

    for key, filename in VALIDATION_OUTPUT_FILES.items():
        path = validation_output_dir / filename
        checks[f"file:{filename}"], payloads[key] = _load_json_object(path)

    if "preflight" in payloads:
        checks["preflight_passed"] = _check_preflight_payload(payloads["preflight"])
    if "smoke" in payloads:
        checks["smoke_passed"] = _check_smoke_payload(payloads["smoke"])
    if "load" in payloads:
        checks["load_passed"] = _check_load_payload(payloads["load"])

    return StagingAcceptanceResult(
        passed=all(value == "ok" for value in checks.values()),
        checks=checks,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check saved GCP staging acceptance evidence")
    parser.add_argument(
        "--validation-output-dir",
        type=Path,
        default=Path("deploy/gcp/validation-output"),
        help="Directory containing preflight.json, smoke.json, and load.json.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root for artifact preflight. Defaults to chatbot-service checkout.",
    )
    parser.add_argument(
        "--skip-artifact-check",
        action="store_true",
        help="Only evaluate saved validation output files.",
    )
    args = parser.parse_args(argv)

    result = check_staging_acceptance(
        args.validation_output_dir,
        root=args.root,
        include_artifact_check=not args.skip_artifact_check,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if not result.passed:
        raise SystemExit(1)


def _load_json_object(path: Path) -> tuple[str, dict[str, Any]]:
    if not path.exists():
        return "failed: missing", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"failed: {type(exc).__name__}", {}
    if not isinstance(payload, dict):
        return "failed: not_object", {}
    return "ok", payload


def _check_preflight_payload(payload: dict[str, Any]) -> str:
    preflight = payload.get("preflight")
    if not isinstance(preflight, dict):
        return "failed: missing preflight object"
    if preflight.get("passed") is not True:
        return "failed: preflight did not pass"
    return "ok"


def _check_smoke_payload(payload: dict[str, Any]) -> str:
    preflight_status = _check_preflight_payload(payload)
    if preflight_status != "ok":
        return preflight_status
    smoke = payload.get("smoke")
    if not isinstance(smoke, dict):
        return "failed: missing smoke object"
    required_true = ("health_ok", "ask_ok", "conversation_ok", "feedback_ok")
    failed_flags = [key for key in required_true if smoke.get(key) is not True]
    if failed_flags:
        return "failed: false smoke flags " + ", ".join(failed_flags)
    if not str(smoke.get("conversation_id", "")).strip():
        return "failed: missing conversation_id"
    if not str(smoke.get("message_id", "")).strip():
        return "failed: missing message_id"
    errors = smoke.get("errors", [])
    if errors:
        return "failed: smoke errors present"
    return "ok"


def _check_load_payload(payload: dict[str, Any]) -> str:
    preflight_status = _check_preflight_payload(payload)
    if preflight_status != "ok":
        return preflight_status
    evaluations = payload.get("evaluations")
    if not isinstance(evaluations, dict):
        return "failed: missing evaluations object"
    failed_evaluations = [
        key
        for key in ("cold", "warm", "warmup")
        if not isinstance(evaluations.get(key), dict) or evaluations[key].get("passed") is not True
    ]
    if failed_evaluations:
        return "failed: failed evaluations " + ", ".join(failed_evaluations)
    for run_name in ("cold", "warm"):
        run = payload.get(run_name)
        if not isinstance(run, dict):
            return f"failed: missing {run_name} run"
        if int(run.get("total", 0)) <= 0:
            return f"failed: {run_name} total was not positive"
        if int(run.get("failed", 0)) != 0:
            return f"failed: {run_name} had request failures"
    return "ok"


__all__ = [
    "StagingAcceptanceResult",
    "VALIDATION_OUTPUT_FILES",
    "check_staging_acceptance",
    "main",
]


if __name__ == "__main__":
    main()
