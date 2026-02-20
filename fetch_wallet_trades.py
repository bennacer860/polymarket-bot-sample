#!/usr/bin/env python3
"""CLI for fetching Polymarket wallet trade history and exporting to CSV.

Usage:
    python fetch_wallet_trades.py \
        --wallet 0xABC... \
        --start 2026-02-20 \
        --end 2026-02-21 \
        --output wallet_trades.csv \
        --min-price 0.95
"""

import argparse
import sys
from datetime import datetime

from pytz import timezone as pytz_timezone

from src.logging_config import setup_logging
from src.trade_fetcher import (
    fetch_trades_for_wallet,
    print_summary,
    write_trades_csv,
)


def parse_date(date_str: str) -> int:
    """
    Parse a YYYY-MM-DD date string into a Unix timestamp (start of day, EST).

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Unix timestamp (seconds) for start of the given day in EST.
    """
    est_tz = pytz_timezone("US/Eastern")
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt_est = est_tz.localize(dt)
    return int(dt_est.timestamp())


def parse_date_end(date_str: str) -> int:
    """
    Parse a YYYY-MM-DD date string into a Unix timestamp for end of day (23:59:59 EST).

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Unix timestamp (seconds) for end of the given day in EST.
    """
    est_tz = pytz_timezone("US/Eastern")
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    dt_est = est_tz.localize(dt)
    return int(dt_est.timestamp())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Polymarket wallet trade history and export to CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all trades for a wallet on a specific day
  python fetch_wallet_trades.py --wallet 0xABC... --start 2026-02-20

  # Fetch trades in a date range with min price filter
  python fetch_wallet_trades.py --wallet 0xABC... --start 2026-02-19 --end 2026-02-20 --min-price 0.95

  # Save to a custom output file
  python fetch_wallet_trades.py --wallet 0xABC... --start 2026-02-20 --output my_trades.csv
        """,
    )
    parser.add_argument(
        "--wallet",
        required=True,
        help="Polymarket proxy wallet address (0x...)",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start date (inclusive, YYYY-MM-DD in EST)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="End date (inclusive, YYYY-MM-DD in EST). Defaults to same as start date.",
    )
    parser.add_argument(
        "--output",
        default="wallet_trades.csv",
        help="Output CSV file path (default: wallet_trades.csv)",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        default=None,
        help="Only include trades at or above this price (e.g. 0.95 for sweep analysis)",
    )

    args = parser.parse_args()

    setup_logging()

    # Parse date range
    start_ts = parse_date(args.start)
    end_date = args.end if args.end else args.start
    end_ts = parse_date_end(end_date)

    est_tz = pytz_timezone("US/Eastern")
    start_dt = datetime.fromtimestamp(start_ts, tz=est_tz)
    end_dt = datetime.fromtimestamp(end_ts, tz=est_tz)

    print(f"Wallet:     {args.wallet}")
    print(f"Date range: {start_dt:%Y-%m-%d %H:%M:%S} — {end_dt:%Y-%m-%d %H:%M:%S} EST")
    if args.min_price is not None:
        print(f"Min price:  {args.min_price}")
    print(f"Output:     {args.output}")
    print()

    # Fetch trades
    trades = fetch_trades_for_wallet(
        wallet=args.wallet,
        start_ts=start_ts,
        end_ts=end_ts,
        min_price=args.min_price,
    )

    # Write CSV
    write_trades_csv(trades, args.output)

    # Print summary
    print_summary(trades)

    return 0


if __name__ == "__main__":
    sys.exit(main())
