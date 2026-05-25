from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class StoredMessage:
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
