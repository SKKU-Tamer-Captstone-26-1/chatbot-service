"""ai-chatbot-service entrypoint."""
from __future__ import annotations

import argparse
import asyncio
import logging

from chatbot_service.config import load_config
from chatbot_service.server import serve


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ONTHEBLOCK ai-chatbot-service")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="load config and print the configured listen address without starting gRPC",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    if args.check_config:
        print(f"chatbot-service configured on {config.service_addr}")
        return

    asyncio.run(serve(config))


if __name__ == "__main__":
    main()
