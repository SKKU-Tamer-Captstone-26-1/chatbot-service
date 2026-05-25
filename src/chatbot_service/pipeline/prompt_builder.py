from __future__ import annotations

import json

from chatbot_service.pipeline.context_builder import GroundedContext

PROMPT_VERSION = "chatbot-grounded-ko-v1"


class PromptBuilder:
    def build_system_prompt(self) -> str:
        return (
            "You are the ONTHEBLOCK app chatbot. Answer in concise, polite Korean. "
            "Only use facts in the provided grounded context. Do not invent alcohols, "
            "venues, prices, distance, inventory, availability, user preferences, or "
            "rankings. Recommendation-service results are already ranked; never rerank "
            "or add new candidates. If facts are missing, say the data is unavailable."
        )

    def build_context_json(self, context: GroundedContext) -> str:
        return json.dumps(
            {
                "intent": context.intent,
                "facts": context.facts,
                "missing_facts": context.missing_facts,
                "confidence": context.confidence,
                "prompt_version": PROMPT_VERSION,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
