#!/usr/bin/env python3
"""Alternate entry point for running the trading bot by slug."""

import asyncio
import sys

from src.logging_config import setup_logging
from src.trading_bot import run_bot


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python run_bot.py <event-slug>", file=sys.stderr)
        return 1

    slug = sys.argv[1]
    setup_logging()
    success = asyncio.run(run_bot(slug))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
