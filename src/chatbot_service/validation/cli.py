from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict

from chatbot_service.validation.client import run_load_validation, run_smoke_validation
from chatbot_service.validation.config import load_validation_config
from chatbot_service.validation.preflight import run_preflight_checks
from chatbot_service.validation.service_metrics import read_service_metrics
from chatbot_service.validation.summary import (
    evaluate_thresholds,
    evaluate_warmup_improvement,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate chatbot-service staging runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Run config and dependency preflight checks only")
    subparsers.add_parser("smoke", help="Run health, AskChatbot, conversation, and feedback checks")
    subparsers.add_parser("load", help="Run cold and warm AskChatbot load validation passes")
    args = parser.parse_args(argv)

    config = load_validation_config()
    preflight = asyncio.run(run_preflight_checks(config))
    if not preflight.passed:
        print(json.dumps({"preflight": asdict(preflight)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if args.command == "preflight":
        print(json.dumps({"preflight": asdict(preflight)}, ensure_ascii=False, indent=2))
        return

    if args.command == "smoke":
        result = asyncio.run(run_smoke_validation(config))
        print(
            json.dumps(
                {"preflight": asdict(preflight), "smoke": asdict(result)},
                ensure_ascii=False,
                indent=2,
            )
        )
        if not result.passed:
            raise SystemExit(1)
        return

    cold = asyncio.run(run_load_validation(config, name="cold"))
    warm = asyncio.run(run_load_validation(config, name="warm"))
    cold_eval = evaluate_thresholds(cold, p95_threshold_ms=config.p95_threshold_ms)
    warm_eval = evaluate_thresholds(warm, p95_threshold_ms=config.p95_threshold_ms)
    warmup_eval = evaluate_warmup_improvement(
        cold,
        warm,
        min_improvement_ratio=config.cache_warmup_min_improvement_ratio,
    )
    payload = {
        "preflight": asdict(preflight),
        "cold": asdict(cold),
        "warm": asdict(warm),
        "service_metrics": read_service_metrics(config),
        "evaluations": {
            "cold": asdict(cold_eval),
            "warm": asdict(warm_eval),
            "warmup": asdict(warmup_eval),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not (cold_eval.passed and warm_eval.passed and warmup_eval.passed):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
