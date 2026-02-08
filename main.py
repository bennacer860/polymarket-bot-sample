#!/usr/bin/env python3
"""CLI entry point for Polymarket bot."""

import argparse
import asyncio
import sys

from src.logging_config import setup_logging, get_logger
from src.gamma_client import fetch_event_by_slug, resolve_token_for_direction
from src.clob_client import place_limit_order
from src.trading_bot import run_bot

logger = get_logger(__name__)


def cmd_trade(slug: str, price: float, direction: str, size: float | None, amount: float | None) -> int:
    """Single trade mode: place a limit order."""
    setup_logging()

    event = fetch_event_by_slug(slug)
    if not event:
        logger.error("Event not found. Check the slug and Polymarket URL.")
        return 1

    markets = event.get("markets") or []
    if len(markets) != 1:
        logger.error("Expected exactly 1 market for this trade, got %d", len(markets))
        return 1

    market = markets[0]
    token_id = resolve_token_for_direction(market, direction)
    if not token_id:
        return 1

    if amount is not None:
        size = amount / price
        logger.info("Computed size=%.4f from amount=$%.2f at price=%.4f", size, amount, price)

    resp = place_limit_order(token_id=token_id, price=price, size=size, side="BUY")
    if resp is None:
        return 1

    if resp.get("success"):
        logger.info("Trade placed: orderId=%s", resp.get("orderId"))
        return 0

    logger.warning("Trade failed: %s", resp.get("errorMsg", "Unknown error"))
    return 1


def cmd_bot(slug: str) -> int:
    """Trading bot mode: wait for event end, then place order on winning side."""
    setup_logging()
    success = asyncio.run(run_bot(slug))
    return 0 if success else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Polymarket Bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    trade_parser = subparsers.add_parser("trade", help="Place a single test limit order")
    trade_parser.add_argument("--slug", required=True, help="Event slug from Polymarket URL")
    trade_parser.add_argument("--price", type=float, required=True, help="Limit price (0.0 - 1.0)")
    trade_parser.add_argument(
        "--direction",
        required=True,
        choices=["up", "down", "yes", "no"],
        help="Direction to bet on",
    )
    size_group = trade_parser.add_mutually_exclusive_group(required=True)
    size_group.add_argument(
        "--size",
        type=float,
        help="Order size in shares.",
    )
    size_group.add_argument(
        "--amount",
        type=float,
        metavar="DOLLARS",
        help="Order amount in dollars. Size is computed as amount/price.",
    )

    bot_parser = subparsers.add_parser("bot", help="Run trading bot for 15-min crypto event")
    bot_parser.add_argument("--slug", required=True, help="Event slug from Polymarket URL")

    args = parser.parse_args()

    if args.command == "trade":
        return cmd_trade(args.slug, args.price, args.direction, args.size, args.amount)
    if args.command == "bot":
        return cmd_bot(args.slug)

    return 1


if __name__ == "__main__":
    sys.exit(main())
