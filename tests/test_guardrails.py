from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.pipeline.context_builder import GroundedContext
from chatbot_service.pipeline.guardrails import Guardrails


def test_guardrails_refuse_out_of_scope():
    answer = Guardrails().enforce(
        ChatbotIntent.OUT_OF_SCOPE,
        GroundedContext(intent=ChatbotIntent.OUT_OF_SCOPE.value),
    )

    assert answer is not None
    assert answer.refused is True
    assert answer.refusal_reason == "OUT_OF_SCOPE"


def test_guardrails_return_no_answer_when_evidence_missing():
    answer = Guardrails().enforce(
        ChatbotIntent.RECOMMEND_BEVERAGE,
        GroundedContext(
            intent=ChatbotIntent.RECOMMEND_BEVERAGE.value,
            missing_facts=["recommendation_service_results"],
        ),
    )

    assert answer is not None
    assert answer.intent == ChatbotIntent.INSUFFICIENT_DATA
    assert answer.refused is False
    assert answer.missing_facts == ["recommendation_service_results"]
