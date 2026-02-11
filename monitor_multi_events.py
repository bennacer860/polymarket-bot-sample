#!/usr/bin/env python3
"""CLI for multi-event and continuous 15-minute market monitoring."""

import argparse
import sys

from src.logging_config import setup_logging
from src.monitors.multi_event_monitor import MultiEventMonitor
from src.monitors.continuous_15min_monitor import ContinuousFifteenMinMonitor
from src.markets.fifteen_min import MARKET_IDS


def cmd_multi_event(slugs: list[str], output: str, ws_url: str | None, ticker_output: str) -> int:
    """Monitor multiple event slugs simultaneously."""
    setup_logging()
    
    monitor = MultiEventMonitor(
        event_slugs=slugs,
        output_file=output,
        ws_url=ws_url,
        ticker_change_file=ticker_output,
    )
    
    monitor.run_sync()
    return 0


def cmd_continuous_15min(markets: list[str], output: str, ws_url: str | None, ticker_output: str) -> int:
    """Continuously monitor 15-minute crypto markets."""
    setup_logging()
    
    # Validate market selections
    invalid_markets = [m for m in markets if m not in MARKET_IDS]
    if invalid_markets:
        print(f"Error: Invalid market selections: {', '.join(invalid_markets)}")
        print(f"Valid options: {', '.join(MARKET_IDS.keys())}")
        return 1
    
    monitor = ContinuousFifteenMinMonitor(
        market_selections=markets,
        output_file=output,
        ws_url=ws_url,
        ticker_change_file=ticker_output,
    )
    
    monitor.run_sync()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Polymarket Multi-Event Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Multi-event monitor
    multi_parser = subparsers.add_parser(
        "multi",
        help="Monitor multiple event slugs simultaneously"
    )
    multi_parser.add_argument(
        "--slugs",
        nargs="+",
        required=True,
        help="Event slugs to monitor (space-separated)"
    )
    multi_parser.add_argument(
        "--output",
        default="bids_0999.csv",
        help="Output CSV file (default: bids_0999.csv)"
    )
    multi_parser.add_argument(
        "--ticker-output",
        default="ticker_changes.csv",
        help="Ticker change events CSV file (default: ticker_changes.csv)"
    )
    multi_parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)"
    )

    # Continuous 15-minute monitor
    continuous_parser = subparsers.add_parser(
        "continuous-15min",
        help="Continuously monitor 15-minute crypto markets"
    )
    continuous_parser.add_argument(
        "--markets",
        nargs="+",
        required=True,
        choices=list(MARKET_IDS.keys()),
        help="Crypto markets to monitor (e.g., BTC ETH SOL XRP)"
    )
    continuous_parser.add_argument(
        "--output",
        default="bids_0999.csv",
        help="Output CSV file (default: bids_0999.csv)"
    )
    continuous_parser.add_argument(
        "--ticker-output",
        default="ticker_changes.csv",
        help="Ticker change events CSV file (default: ticker_changes.csv)"
    )
    continuous_parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)"
    )

    args = parser.parse_args()

    if args.command == "multi":
        return cmd_multi_event(args.slugs, args.output, args.ws_url, args.ticker_output)
    if args.command == "continuous-15min":
        return cmd_continuous_15min(args.markets, args.output, args.ws_url, args.ticker_output)

    return 1


if __name__ == "__main__":
    sys.exit(main())
