from __future__ import annotations

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
        return text
