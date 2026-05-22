from assistant_service.domain.intents import AssistantIntent
from assistant_service.domain.schemas import AssistantAnswer, AssistantCard
from .context_builder import GroundedContext


class ResponseBuilder:
    def build_from_grounded_text(self, intent: AssistantIntent, answer: str, context: GroundedContext) -> AssistantAnswer:
        # Cards should be generated from recommendation-service results, not from LLM text.
        cards: list[AssistantCard] = []
        return AssistantAnswer(
            intent=intent,
            answer=answer,
            confidence=context.confidence,
            cards=cards,
            used_sources=context.facts.get("used_sources", {}),
            missing_facts=context.missing_facts,
        )
