from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import ChatbotAnswer, ChatbotCard, ChatbotResponseStatus
from chatbot_service.pipeline.context_builder import GroundedContext


class Guardrails:
    def enforce(self, intent: ChatbotIntent, context: GroundedContext) -> ChatbotAnswer | None:
        if intent == ChatbotIntent.OUT_OF_SCOPE:
            return ChatbotAnswer(
                intent=intent,
                answer=(
                    "저는 ONTHEBLOCK의 술 추천, 취향, 주변 장소 정보에 대해서만 "
                    "도와드릴 수 있어요."
                ),
                confidence=1.0,
                status=ChatbotResponseStatus.REFUSED,
                refused=True,
                refusal_reason="OUT_OF_SCOPE",
            )
        if _has_inactive_profile(context):
            profile_status = str(context.facts.get("profile_status", "PROFILE_STATUS_UNSPECIFIED"))
            profile_revision = int(context.facts.get("profile_revision", 0) or 0)
            return ChatbotAnswer(
                intent=ChatbotIntent.PROFILE_STATUS,
                answer=_profile_status_answer(profile_status),
                confidence=1.0,
                status=ChatbotResponseStatus.INSUFFICIENT_DATA,
                profile_status=profile_status,
                refused=False,
                refusal_reason="INSUFFICIENT_DATA",
                cards=[
                    ChatbotCard(
                        card_type="CHATBOT_CARD_TYPE_PROFILE_STATUS",
                        title=profile_status,
                        display_reason=_profile_status_answer(profile_status),
                        detail={
                            "profile_status": {
                                "status": profile_status,
                                "profile_revision": profile_revision,
                            }
                        },
                    )
                ],
                used_sources=context.facts.get("used_sources", {}),
                missing_facts=context.missing_facts,
            )
        if "recommendation_service_unavailable" in context.missing_facts:
            return ChatbotAnswer(
                intent=ChatbotIntent.INSUFFICIENT_DATA,
                answer="추천 데이터를 일시적으로 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
                confidence=1.0,
                status=ChatbotResponseStatus.INSUFFICIENT_DATA,
                refused=False,
                refusal_reason="RECOMMENDATION_SERVICE_UNAVAILABLE",
                missing_facts=context.missing_facts,
            )
        if _has_missing_venue_inputs(context):
            return ChatbotAnswer(
                intent=ChatbotIntent.INSUFFICIENT_DATA,
                answer=_missing_venue_inputs_answer(context.missing_facts),
                confidence=1.0,
                status=ChatbotResponseStatus.INSUFFICIENT_DATA,
                refused=False,
                refusal_reason="INSUFFICIENT_DATA",
                missing_facts=context.missing_facts,
                follow_up_questions=_missing_venue_follow_ups(context.missing_facts),
            )
        if _has_empty_recommendations(context):
            if _has_diversity_candidate_exhaustion(context):
                return ChatbotAnswer(
                    intent=ChatbotIntent.INSUFFICIENT_DATA,
                    answer=(
                        "요청하신 조건에서 다른 추천 후보를 더 찾지 못했어요. "
                        "조건을 바꾸거나 잠시 뒤에 다시 요청해 주세요."
                    ),
                    confidence=1.0,
                    status=ChatbotResponseStatus.INSUFFICIENT_DATA,
                    refused=False,
                    refusal_reason="INSUFFICIENT_DATA",
                    missing_facts=context.missing_facts,
                )
            return ChatbotAnswer(
                intent=ChatbotIntent.INSUFFICIENT_DATA,
                answer=(
                    "아직 추천 후보가 충분하지 않아요. "
                    "추천 데이터가 준비된 뒤 다시 시도해 주세요."
                ),
                confidence=1.0,
                status=ChatbotResponseStatus.INSUFFICIENT_DATA,
                refused=False,
                refusal_reason="INSUFFICIENT_DATA",
                missing_facts=context.missing_facts,
            )
        if not context.has_evidence:
            return ChatbotAnswer(
                intent=ChatbotIntent.INSUFFICIENT_DATA,
                answer="현재 ONTHEBLOCK 데이터에서 신뢰할 수 있는 추천 근거를 찾지 못했어요.",
                confidence=1.0,
                status=ChatbotResponseStatus.INSUFFICIENT_DATA,
                refused=False,
                refusal_reason="INSUFFICIENT_DATA",
                missing_facts=context.missing_facts,
            )
        return None


def _has_inactive_profile(context: GroundedContext) -> bool:
    profile_status = str(context.facts.get("profile_status", ""))
    if "active_recommendation_profile" in context.missing_facts:
        return True
    return bool(profile_status) and profile_status not in {"PROFILE_STATUS_ACTIVE", "ACTIVE"}


def _has_empty_recommendations(context: GroundedContext) -> bool:
    return any(
        fact in context.missing_facts
        for fact in (
            "beverage_recommendation_candidates",
            "fresh_venue_recommendation_candidates",
            "beverage_recommendation_candidates_exhausted",
            "venue_recommendation_candidates_exhausted",
        )
    )


def _has_diversity_candidate_exhaustion(context: GroundedContext) -> bool:
    return any(
        fact in context.missing_facts
        for fact in (
            "beverage_recommendation_candidates_exhausted",
            "venue_recommendation_candidates_exhausted",
        )
    )


def _has_missing_venue_inputs(context: GroundedContext) -> bool:
    if context.intent not in {
        ChatbotIntent.FIND_NEARBY_VENUE.value,
        ChatbotIntent.COMPARE_PURCHASE_OPTIONS.value,
    }:
        return False
    return any(
        fact in context.missing_facts
        for fact in ("detailed_location", "selected_beverage_id")
    )


def _missing_venue_inputs_answer(missing_facts: list[str]) -> str:
    if "detailed_location" in missing_facts and "selected_beverage_id" in missing_facts:
        return (
            "장소 추천을 하려면 현재 위치와 기준이 될 술 정보가 필요해요. "
            "먼저 추천받은 술을 선택하고 위치 권한을 허용한 뒤 다시 물어봐 주세요."
        )
    if "detailed_location" in missing_facts:
        return "장소 추천을 하려면 현재 위치가 필요해요. 위치 권한을 허용한 뒤 다시 물어봐 주세요."
    return (
        "장소 추천을 하려면 기준이 될 술을 먼저 선택해야 해요. "
        "추천 카드에서 술을 선택한 뒤 근처 장소를 물어봐 주세요."
    )


def _missing_venue_follow_ups(missing_facts: list[str]) -> list[str]:
    questions: list[str] = []
    if "selected_beverage_id" in missing_facts:
        questions.append("어떤 술을 기준으로 장소를 찾아드릴까요?")
    if "detailed_location" in missing_facts:
        questions.append("현재 위치를 사용해도 될까요?")
    return questions


def _profile_status_answer(profile_status: str) -> str:
    if profile_status in {"PROFILE_STATUS_MISSING", "MISSING"}:
        return (
            "아직 추천 프로필이 준비되지 않았어요. "
            "먼저 취향 설문을 완료하거나 설문 처리가 끝날 때까지 기다려 주세요."
        )
    if profile_status in {"PROFILE_STATUS_PENDING_GENERATION", "PENDING_GENERATION"}:
        return "추천 프로필을 생성 중이에요. 설문 처리가 끝난 뒤 다시 시도해 주세요."
    if profile_status in {"PROFILE_STATUS_STALE", "STALE"}:
        return "추천 프로필을 갱신해야 해요. 최신 추천 프로필이 준비되면 다시 추천해 드릴게요."
    if profile_status in {"PROFILE_STATUS_FAILED_GENERATION", "FAILED_GENERATION"}:
        return (
            "추천 프로필 생성에 실패했어요. "
            "잠시 후 다시 시도하거나 취향 설문 상태를 확인해 주세요."
        )
    return "추천 프로필이 아직 활성 상태가 아니어서 신뢰할 수 있는 추천을 만들 수 없어요."
