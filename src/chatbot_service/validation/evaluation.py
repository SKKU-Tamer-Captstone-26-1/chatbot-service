from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.protobuf import json_format

ALLOWED_CHECKS = {
    "grounding",
    "no_answer",
    "refusal",
    "ranking_integrity",
    "korean_tone",
    "price_inventory_uncertainty",
}

REQUIRED_SUITE_CHECKS = {
    "golden_cases.yaml": "grounding",
    "no_answer_cases.yaml": "no_answer",
    "out_of_scope_cases.yaml": "refusal",
    "ranking_integrity_cases.yaml": "ranking_integrity",
    "korean_tone_cases.yaml": "korean_tone",
    "price_inventory_uncertainty_cases.yaml": "price_inventory_uncertainty",
}

PRICE_EXPERIENCE_WARNING = (
    "이 추천은 검증된 가격 관측값과 사람들의 경험적 의견을 바탕으로 만든 참고용 추천입니다."
)

UNCERTAINTY_TERMS = (
    "참고",
    "관측",
    "달라질 수",
    "확인",
    "불확실",
    "현재와 다를 수",
)

INTERNAL_TERMS = (
    "used_sources",
    "prompt",
    "metadata",
    "authorization",
    "x-user-id",
    "jwt",
)

LIVE_TRUTH_PHRASES = (
    "현재 매장 가격은",
    "실제 매장 가격은",
    "실시간 가격",
    "현재 판매가는",
    "재고가 있습니다",
    "판매 중입니다",
    "보장",
    "확정",
)


@dataclass(frozen=True)
class FixtureValidationResult:
    passed: bool
    case_count: int
    suites: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def validate_evaluation_fixtures(root: Path | str = Path("evaluation")) -> FixtureValidationResult:
    root = Path(root)
    failures: list[str] = []
    suites: dict[str, int] = {}
    case_count = 0

    for filename, required_check in REQUIRED_SUITE_CHECKS.items():
        path = root / filename
        if not path.exists():
            failures.append(f"{filename}: missing fixture file")
            continue
        try:
            cases = load_fixture_file(path)
        except ValueError as exc:
            failures.append(f"{filename}: {exc}")
            continue
        suites[filename.removesuffix(".yaml")] = len(cases)
        case_count += len(cases)
        if not cases:
            failures.append(f"{filename}: must contain at least one case")
        for index, case in enumerate(cases, start=1):
            _validate_case(filename, index, case, required_check, failures)

    return FixtureValidationResult(
        passed=not failures,
        case_count=case_count,
        suites=suites,
        failures=failures,
    )


def load_all_fixtures(root: Path | str = Path("evaluation")) -> list[dict[str, Any]]:
    root = Path(root)
    cases: list[dict[str, Any]] = []
    for filename in REQUIRED_SUITE_CHECKS:
        path = root / filename
        if not path.exists():
            continue
        for case in load_fixture_file(path):
            case = dict(case)
            case["suite"] = filename.removesuffix(".yaml")
            cases.append(case)
    return cases


def load_fixture_file(path: Path | str) -> list[dict[str, Any]]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        value = json.loads(stripped)
        if not isinstance(value, list):
            raise ValueError("fixture file must contain a list")
        return [_ensure_case_dict(item, index, path.name) for index, item in enumerate(value, 1)]
    return _parse_simple_yaml_sequence(text, path.name)


def assert_response_matches_case(response: Any, chatbot_pb2: Any, case: dict[str, Any]) -> None:
    expected_status = str(case.get("expected_status", "")).strip()
    if expected_status:
        actual_status = _enum_name(chatbot_pb2.ChatbotResponseStatus, response.status)
        if actual_status != _response_status_name(expected_status):
            raise ValueError(
                f"{case['name']}: expected status {expected_status}, got {actual_status}"
            )

    expected_intent = str(case.get("expected_intent", "")).strip()
    if expected_intent:
        actual_intent = _enum_name(chatbot_pb2.ChatbotIntent, response.intent)
        if actual_intent != _intent_name(expected_intent):
            raise ValueError(
                f"{case['name']}: expected intent {expected_intent}, got {actual_intent}"
            )

    checks = set(_string_list(case.get("checks", [])))
    if "grounding" in checks:
        assert_grounded_response(response, chatbot_pb2)
    if "no_answer" in checks:
        _assert_no_answer_response(response, chatbot_pb2, case)
    if "refusal" in checks:
        _assert_refusal_response(response, chatbot_pb2, case)
    if "ranking_integrity" in checks:
        _assert_expected_result_order(response, chatbot_pb2, case)
    if "korean_tone" in checks:
        _assert_korean_tone(response.answer, case_name=str(case["name"]), case=case)
    if "price_inventory_uncertainty" in checks:
        _assert_expected_terms(response.answer, case)
        _assert_uncertainty_language(response.answer, response.cards)

    _assert_expected_terms(response.answer, case)
    _assert_expected_card_types(response, chatbot_pb2, case)


def assert_grounded_response(response: Any, chatbot_pb2: Any) -> None:
    _assert_korean_tone(response.answer, case_name="runtime response", case={})
    if response.status == chatbot_pb2.CHATBOT_RESPONSE_STATUS_ANSWERED:
        if not response.cards:
            raise ValueError("answered response had no cards")
        _assert_answered_cards_grounded(response, chatbot_pb2)
        _assert_uncertainty_language(response.answer, response.cards)
    elif response.status == chatbot_pb2.CHATBOT_RESPONSE_STATUS_INSUFFICIENT_DATA:
        if not response.missing_facts:
            raise ValueError("insufficient-data response had no missing_facts")
    elif response.status == chatbot_pb2.CHATBOT_RESPONSE_STATUS_REFUSED:
        if not response.refused:
            raise ValueError("refused response did not set refused=true")
    else:
        raise ValueError("response status was unspecified")


def _validate_case(
    filename: str,
    index: int,
    case: dict[str, Any],
    required_check: str,
    failures: list[str],
) -> None:
    prefix = f"{filename}[{index}]"
    name = str(case.get("name", "")).strip()
    if not name:
        failures.append(f"{prefix}: name is required")
    if not str(case.get("user_message", "")).strip():
        failures.append(f"{prefix}: user_message is required")
    checks = _string_list(case.get("checks", []))
    if required_check not in checks:
        failures.append(f"{prefix}: checks must include {required_check}")
    unknown = sorted(set(checks) - ALLOWED_CHECKS)
    if unknown:
        failures.append(f"{prefix}: unsupported checks {', '.join(unknown)}")
    if not str(case.get("expected_intent", "")).strip():
        failures.append(f"{prefix}: expected_intent is required")
    if not str(case.get("expected_status", "")).strip():
        failures.append(f"{prefix}: expected_status is required")

    if "grounding" in checks and not _string_list(case.get("expected_card_types", [])):
        failures.append(f"{prefix}: grounding cases need expected_card_types")
    if "no_answer" in checks and not (
        _string_list(case.get("expected_missing_facts", []))
        or _string_list(case.get("expected_answer_contains", []))
    ):
        failures.append(f"{prefix}: no_answer cases need missing facts or answer text")
    if "refusal" in checks and case.get("expected_refused") is not True:
        failures.append(f"{prefix}: refusal cases need expected_refused: true")
    if "ranking_integrity" in checks and len(_string_list(case.get("expected_result_ids", []))) < 2:
        failures.append(f"{prefix}: ranking_integrity cases need at least two result IDs")
    if "korean_tone" in checks:
        if int(case.get("max_answer_chars", 0) or 0) <= 0:
            failures.append(f"{prefix}: korean_tone cases need max_answer_chars")
        if not _string_list(case.get("forbidden_answer_terms", [])):
            failures.append(f"{prefix}: korean_tone cases need forbidden_answer_terms")
    if "price_inventory_uncertainty" in checks:
        if not _string_list(case.get("required_answer_terms", [])):
            failures.append(f"{prefix}: uncertainty cases need required_answer_terms")
        if not _string_list(case.get("forbidden_answer_terms", [])):
            failures.append(f"{prefix}: uncertainty cases need forbidden_answer_terms")


def _assert_no_answer_response(response: Any, chatbot_pb2: Any, case: dict[str, Any]) -> None:
    if response.status != chatbot_pb2.CHATBOT_RESPONSE_STATUS_INSUFFICIENT_DATA:
        raise ValueError(f"{case['name']}: expected insufficient-data response")
    for fact in _string_list(case.get("expected_missing_facts", [])):
        if fact not in response.missing_facts:
            raise ValueError(f"{case['name']}: missing expected fact {fact}")


def _assert_refusal_response(response: Any, chatbot_pb2: Any, case: dict[str, Any]) -> None:
    if response.status != chatbot_pb2.CHATBOT_RESPONSE_STATUS_REFUSED:
        raise ValueError(f"{case['name']}: expected refused response")
    if not response.refused:
        raise ValueError(f"{case['name']}: expected refused=true")
    reason = str(case.get("expected_refusal_reason", "")).strip()
    if reason and response.refusal_reason != reason:
        raise ValueError(f"{case['name']}: expected refusal reason {reason}")


def _assert_answered_cards_grounded(response: Any, chatbot_pb2: Any) -> None:
    beverage_result_ids = list(response.used_sources.beverage_result_ids)
    venue_result_ids = list(response.used_sources.venue_result_ids)
    beverage_ranks: list[int] = []
    venue_ranks: list[int] = []
    for card in response.cards:
        if card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION:
            if card.WhichOneof("detail") != "beverage_recommendation":
                raise ValueError("beverage card had no beverage_recommendation detail")
            detail = card.beverage_recommendation
            _assert_result_id("beverage", detail.result_id, set(beverage_result_ids))
            beverage_ranks.append(detail.rank)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION:
            if card.WhichOneof("detail") != "venue_recommendation":
                raise ValueError("venue card had no venue_recommendation detail")
            detail = card.venue_recommendation
            _assert_result_id("venue", detail.result_id, set(venue_result_ids))
            venue_ranks.append(detail.rank)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_PURCHASE_OPTION:
            if card.WhichOneof("detail") != "purchase_option":
                raise ValueError("purchase card had no purchase_option detail")
            detail = card.purchase_option
            _assert_result_id("purchase", detail.result_id, set(venue_result_ids))
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_COMPARISON:
            if card.WhichOneof("detail") != "comparison":
                raise ValueError("comparison card had no comparison detail")
            for option in card.comparison.options:
                _assert_result_id("comparison purchase", option.result_id, set(venue_result_ids))
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_PROFILE_STATUS:
            if card.WhichOneof("detail") != "profile_status":
                raise ValueError("profile card had no profile_status detail")
        else:
            raise ValueError("answered response used unsupported card type")
    if beverage_ranks and beverage_ranks != sorted(beverage_ranks):
        raise ValueError("beverage recommendation card ranks were not ordered")
    if venue_ranks and venue_ranks != sorted(venue_ranks):
        raise ValueError("recommendation card ranks were not ordered")


def _assert_expected_result_order(response: Any, chatbot_pb2: Any, case: dict[str, Any]) -> None:
    expected = _string_list(case.get("expected_result_ids", []))
    if not expected:
        return
    actual: list[str] = []
    for card in response.cards:
        if card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION:
            actual.append(card.beverage_recommendation.result_id)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION:
            actual.append(card.venue_recommendation.result_id)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_PURCHASE_OPTION:
            actual.append(card.purchase_option.result_id)
    if actual[: len(expected)] != expected:
        raise ValueError(f"{case['name']}: recommendation result order changed")


def _assert_expected_terms(answer: str, case: dict[str, Any]) -> None:
    for expected in _string_list(case.get("expected_answer_contains", [])):
        if expected not in answer:
            raise ValueError(f"{case['name']}: answer did not include {expected}")
    for required in _string_list(case.get("required_answer_terms", [])):
        if required not in answer:
            raise ValueError(f"{case['name']}: answer did not include required term {required}")
    for forbidden in _string_list(case.get("forbidden_answer_terms", [])):
        if forbidden and forbidden.lower() in answer.lower():
            raise ValueError(f"{case['name']}: answer included forbidden term {forbidden}")


def _assert_expected_card_types(response: Any, chatbot_pb2: Any, case: dict[str, Any]) -> None:
    expected = _string_list(case.get("expected_card_types", []))
    if not expected:
        return
    actual = [_enum_name(chatbot_pb2.ChatbotCardType, card.card_type) for card in response.cards]
    for card_type in expected:
        if card_type not in actual:
            raise ValueError(f"{case['name']}: missing expected card type {card_type}")


def _assert_result_id(kind: str, result_id: str, used_result_ids: set[str]) -> None:
    if not result_id:
        raise ValueError(f"{kind} card had no result_id")
    if not used_result_ids:
        raise ValueError(f"{kind} card had no used_sources result IDs")
    if result_id not in used_result_ids:
        raise ValueError(f"{kind} card result_id was not present in used_sources")


def _assert_korean_tone(answer: str, *, case_name: str, case: dict[str, Any]) -> None:
    text = answer.strip()
    if not text:
        raise ValueError(f"{case_name}: answer was empty")
    if not re.search(r"[가-힣]", text):
        raise ValueError(f"{case_name}: answer was not Korean")
    max_chars = int(case.get("max_answer_chars", 700) or 700)
    if len(text) > max_chars:
        raise ValueError(f"{case_name}: answer exceeded {max_chars} characters")
    lowered = text.lower()
    for term in INTERNAL_TERMS:
        if term in lowered:
            raise ValueError(f"{case_name}: answer exposed internal term {term}")


def _assert_uncertainty_language(answer: str, cards: Any) -> None:
    serialized_cards = [_message_to_dict(card) for card in cards]
    serialized = json.dumps(serialized_cards, ensure_ascii=False).lower()
    needs_price_warning = "verified_krw_observations_not_live_truth" in serialized
    needs_uncertainty = needs_price_warning or any(
        marker.lower() in serialized
        for marker in (
            "VENUE_AVAILABILITY_STATUS_UNKNOWN",
            "VENUE_FRESHNESS_STATUS_STALE",
            "VENUE_FRESHNESS_STATUS_EXPIRED",
            "price_freshness_status",
            "inventory_freshness_status",
            "low_inventory_confidence",
        )
    )
    if needs_uncertainty and any(phrase in answer for phrase in LIVE_TRUTH_PHRASES):
        raise ValueError("uncertain price/inventory response overstated live truth")
    if needs_price_warning and PRICE_EXPERIENCE_WARNING not in answer:
        raise ValueError("price observation response did not include required warning")
    if needs_uncertainty and not any(term in answer for term in UNCERTAINTY_TERMS):
        raise ValueError("uncertain price/inventory response did not disclose uncertainty")


def _parse_simple_yaml_sequence(text: str, filename: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_key = ""
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0 and stripped.startswith("- "):
            if current is not None:
                cases.append(current)
            current = {}
            pending_key = ""
            rest = stripped[2:].strip()
            if rest:
                key, value = _split_key_value(rest, filename)
                current[key] = _parse_scalar(value)
            continue
        if current is None:
            raise ValueError("fixture file must start with a list item")
        if indent == 2 and ":" in stripped:
            key, value = _split_key_value(stripped, filename)
            if value == "":
                current[key] = []
                pending_key = key
            else:
                current[key] = _parse_scalar(value)
                pending_key = ""
            continue
        if indent >= 4 and stripped.startswith("- "):
            if not pending_key:
                raise ValueError("nested list item had no parent key")
            current[pending_key].append(_parse_scalar(stripped[2:].strip()))
            continue
        raise ValueError(f"unsupported YAML shape near line: {raw_line}")
    if current is not None:
        cases.append(current)
    return [_ensure_case_dict(item, index, filename) for index, item in enumerate(cases, 1)]


def _split_key_value(raw: str, filename: str) -> tuple[str, str]:
    if ":" not in raw:
        raise ValueError(f"{filename}: expected key: value")
    key, value = raw.split(":", maxsplit=1)
    key = key.strip()
    if not key:
        raise ValueError(f"{filename}: empty key")
    return key, value.strip()


def _parse_scalar(raw: str) -> Any:
    if raw == "":
        return ""
    if raw in {"null", "NULL", "~"}:
        return None
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        return raw


def _ensure_case_dict(value: Any, index: int, filename: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{filename}[{index}] must be an object")
    return dict(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _message_to_dict(message: Any) -> dict[str, Any]:
    return json_format.MessageToDict(message, preserving_proto_field_name=True)


def _enum_name(enum_type: Any, value: int) -> str:
    try:
        return enum_type.Name(value)
    except ValueError:
        return ""


def _intent_name(intent: str) -> str:
    if intent.startswith("CHATBOT_INTENT_"):
        return intent
    return f"CHATBOT_INTENT_{intent}" if intent else "CHATBOT_INTENT_UNSPECIFIED"


def _response_status_name(status: str) -> str:
    if status.startswith("CHATBOT_RESPONSE_STATUS_"):
        return status
    return f"CHATBOT_RESPONSE_STATUS_{status}" if status else "CHATBOT_RESPONSE_STATUS_UNSPECIFIED"
