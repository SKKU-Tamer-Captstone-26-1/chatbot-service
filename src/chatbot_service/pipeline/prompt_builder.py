from __future__ import annotations

import json

from chatbot_service.pipeline.context_builder import GroundedContext

PROMPT_VERSION = "chatbot-grounded-ko-v1"


class PromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "You are the ONTHEBLOCK recommendation assistant. Answer in Korean. "
            "Use only the provided recommendation context. Do not invent beverages, "
            "stores, prices, inventory, ratings, distances, or reasons. If the context "
            "does not contain enough information, say that the service does not have "
            "enough data yet. Do not answer questions unrelated to ONTHEBLOCK beverage "
            "recommendation, survey, or supported service features. Keep the answer "
            "concise and user-friendly. Never expose internal scores unless the context "
            "explicitly marks them as user-visible. Recommendation-service results are "
            "already ranked; never rerank or add new candidates."
        )

    def build_context_json(self, context: GroundedContext) -> str:
        return json.dumps(
            {
                "intent": context.intent,
                "grounded_context": context.facts.get("grounded_recommendation_context", {}),
                "missing_facts": context.missing_facts,
                "prompt_version": PROMPT_VERSION,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
