#!/usr/bin/env python3
"""CLI for multi-event and continuous crypto market monitoring."""

import argparse
import sys

from src.logging_config import setup_logging
from src.monitors.multi_event_monitor import MultiEventMonitor
from src.monitors.continuous_15min_monitor import ContinuousCryptoMonitor
from src.markets.fifteen_min import MARKET_IDS, SUPPORTED_DURATIONS


def cmd_multi_event(slugs: list[str], output: str, ws_url: str | None, market_events_output: str) -> int:
    """Monitor multiple event slugs simultaneously."""
    setup_logging()
    
    monitor = MultiEventMonitor(
        event_slugs=slugs,
        output_file=output,
        ws_url=ws_url,
        market_events_file=market_events_output,
    )
    
    monitor.run_sync()
    return 0


def cmd_continuous(markets: list[str], duration: int, output: str, ws_url: str | None, market_events_output: str) -> int:
    """Continuously monitor crypto markets at the specified duration."""
    setup_logging()
    
    # Validate market selections
    invalid_markets = [m for m in markets if m not in MARKET_IDS]
    if invalid_markets:
        print(f"Error: Invalid market selections: {', '.join(invalid_markets)}")
        print(f"Valid options: {', '.join(MARKET_IDS.keys())}")
        return 1
    
    monitor = ContinuousCryptoMonitor(
        market_selections=markets,
        duration_minutes=duration,
        output_file=output,
        ws_url=ws_url,
        market_events_file=market_events_output,
    )
    
    monitor.run_sync()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Polymarket Multi-Event Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── multi: ad-hoc slug monitoring ────────────────────────────────────────
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
        default="sweeper_analysis.csv",
        help="Unified CSV file for all events (bids, asks, market events) (default: sweeper_analysis.csv)"
    )
    multi_parser.add_argument(
        "--market-events-output",
        default=None,
        help="[DEPRECATED] Market events are now included in the unified output file. This parameter is ignored."
    )
    multi_parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)"
    )

    # ── continuous: duration-flexible auto-rolling monitor ────────────────────
    continuous_parser = subparsers.add_parser(
        "continuous",
        help="Continuously monitor crypto markets (auto-rolls to new windows)"
    )
    continuous_parser.add_argument(
        "--markets",
        nargs="+",
        required=True,
        choices=list(MARKET_IDS.keys()),
        help="Crypto markets to monitor (e.g., BTC ETH SOL XRP)"
    )
    continuous_parser.add_argument(
        "--duration",
        type=int,
        default=15,
        choices=sorted(SUPPORTED_DURATIONS),
        help="Market duration in minutes (default: 15)"
    )
    continuous_parser.add_argument(
        "--output",
        default=None,
        help="Unified CSV file for all events (default: sweeper_analysis_{duration}min.csv)"
    )
    continuous_parser.add_argument(
        "--market-events-output",
        default=None,
        help="[DEPRECATED] Market events are now included in the unified output file. This parameter is ignored."
    )
    continuous_parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)"
    )

    # ── backward compat: continuous-15min ────────────────────────────────────
    compat_parser = subparsers.add_parser(
        "continuous-15min",
        help="(Alias for: continuous --duration 15)"
    )
    compat_parser.add_argument(
        "--markets",
        nargs="+",
        required=True,
        choices=list(MARKET_IDS.keys()),
        help="Crypto markets to monitor (e.g., BTC ETH SOL XRP)"
    )
    compat_parser.add_argument(
        "--output",
        default="sweeper_analysis_15min.csv",
        help="Unified CSV file for all events (default: sweeper_analysis_15min.csv)"
    )
    compat_parser.add_argument(
        "--market-events-output",
        default=None,
        help="[DEPRECATED] Market events are now included in the unified output file. This parameter is ignored."
    )
    compat_parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)"
    )

    args = parser.parse_args()

    if args.command == "multi":
        return cmd_multi_event(args.slugs, args.output, args.ws_url, args.market_events_output)
    if args.command == "continuous":
        output = args.output or f"sweeper_analysis_{args.duration}min.csv"
        return cmd_continuous(args.markets, args.duration, output, args.ws_url, args.market_events_output)
    if args.command == "continuous-15min":
        return cmd_continuous(args.markets, 15, args.output, args.ws_url, args.market_events_output)

    return 1


if __name__ == "__main__":
    sys.exit(main())
