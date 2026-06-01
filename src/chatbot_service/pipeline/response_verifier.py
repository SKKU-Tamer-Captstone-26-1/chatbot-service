from __future__ import annotations

import re
from typing import Any

from chatbot_service.pipeline.context_builder import GroundedContext


class ResponseVerificationError(ValueError):
    """Raised when generated text violates grounding requirements."""


class ResponseVerifier:
    def verify(self, answer: str, context: GroundedContext) -> str:
        text = answer.strip()
        if not text:
            raise ResponseVerificationError("LLM answer is empty")
        if not context.has_evidence:
            raise ResponseVerificationError("LLM answer cannot be used without evidence")
        _verify_numbers_are_grounded(text, context)
        _verify_recommendation_claim_mentions_returned_candidate(text, context)
        return text


def _verify_numbers_are_grounded(text: str, context: GroundedContext) -> None:
    numeric_claims = set(
        re.findall(
            r"\d[\d,]*(?:\.\d+)?\s*(?:원|krw|m|미터|km|킬로미터)",
            text,
            re.I,
        )
    )
    if not numeric_claims:
        return
    context_text = _context_text(context)
    missing = [
        claim
        for claim in numeric_claims
        if _normalize_numeric_value(claim) not in context_text
    ]
    if missing:
        raise ResponseVerificationError("LLM answer contains ungrounded numeric facts")


def _verify_recommendation_claim_mentions_returned_candidate(
    text: str,
    context: GroundedContext,
) -> None:
    candidate_names = _candidate_names(context)
    if not candidate_names:
        return
    if any(name and name in text for name in candidate_names):
        return
    if any(token in text for token in ("아래", "카드", "후보", "목록", "반환한 순서")):
        return
    if any(token in text for token in ("추천", "잘 맞", "어울", "마셔", "구매", "방문")):
        raise ResponseVerificationError("LLM answer does not mention a returned candidate")


def _candidate_names(context: GroundedContext) -> list[str]:
    facts = context.facts
    names: list[str] = []
    for item in facts.get("beverage_recommendations", []):
        names.extend(
            _string_values(
                item,
                "name_ko",
                "name_en",
                "name",
                "beverage_name",
            )
        )
    for item in facts.get("venue_recommendations", []):
        names.extend(_string_values(item, "name", "place_name", "beverage_name"))
    return [name for name in names if name]


def _string_values(value: Any, *keys: str) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [str(value.get(key, "")).strip() for key in keys if str(value.get(key, "")).strip()]


def _context_text(context: GroundedContext) -> str:
    return _normalize_number_claim(str(context.facts))


def _normalize_number_claim(value: str) -> str:
    return value.replace(",", "").replace(" ", "").lower()


def _normalize_numeric_value(value: str) -> str:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", value)
    if match is None:
        return ""
    return match.group(0).replace(",", "").lower()
