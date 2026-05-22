"""Build grounded RAG context from service outputs.

This module should not directly read survey DB or map DB.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GroundedContext:
    intent: str
    facts: dict[str, Any] = field(default_factory=dict)
    missing_facts: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def has_evidence(self) -> bool:
        return bool(self.facts)
