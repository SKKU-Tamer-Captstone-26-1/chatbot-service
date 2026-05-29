from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def main() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    from chatbot_service.deployment.gcp_staging_readiness import main as readiness_main

    readiness_main()


if __name__ == "__main__":
    main()
