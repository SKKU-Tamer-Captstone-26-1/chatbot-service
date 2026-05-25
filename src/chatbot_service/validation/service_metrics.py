from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chatbot_service.validation.config import ValidationConfig


def read_service_metrics(config: ValidationConfig) -> dict[str, Any]:
    if not config.service_metrics_path:
        return {"status": "disabled"}
    path = Path(config.service_metrics_path)
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "error": type(exc).__name__, "path": str(path)}
    if not isinstance(payload, dict):
        return {"status": "invalid", "error": "not_object", "path": str(path)}
    return {"status": "ok", "path": str(path), "snapshot": payload}

