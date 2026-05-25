from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import ChatbotAnswer, ChatbotResponseStatus
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
