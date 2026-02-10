#!/usr/bin/env python3
"""
Helper script to find token IDs for a Polymarket event slug.
This makes it easier to get the token_id needed for monitor_book_bids.py
"""

import argparse
import sys

from src.gamma_client import fetch_event_by_slug, get_market_token_ids
from src.logging_config import setup_logging, get_logger
from monitor_book_bids import BookMonitor

logger = get_logger(__name__)


def main():
    """Main entry point."""
    setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Get token IDs for a Polymarket event"
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Event slug from Polymarket URL"
    )
    parser.add_argument(
        "--output",
        default="bids_0999.csv",
        help="Output CSV file for monitoring data (default: bids_0999.csv)"
    )

    args = parser.parse_args()

    # Fetch event details
    event = fetch_event_by_slug(args.slug)
    if not event:
        logger.error("Event not found. Check the slug and Polymarket URL.")
        return 1

    # Display event info
    print(f"\nEvent: {event.get('title', 'Unknown')}")
    print(f"Slug: {args.slug}")
    print("-" * 60)

    # Display markets and tokens
    markets = event.get("markets", [])
    if not markets:
        logger.error("No markets found for this event")
        return 1

    print(f"\nFound {len(markets)} market(s):\n")

    for i, market in enumerate(markets, 1):
        print(f"Market {i}:")
        print(f"  Question: {market.get('question', 'N/A')}")
        print(f"  Closed: {market.get('closed', False)}")

        # Get tokens using get_market_token_ids
        tokens = get_market_token_ids(market)
        if tokens:
            print(f"  Tokens:")
            for token in tokens:
                print(f"    - {token}")
        else:
            print(f"  No tokens found")
        print()

    # Start monitoring the first token ID of the first market
    if markets:
        tokens = get_market_token_ids(markets[0])
        if tokens:
            token_id = tokens[0]
            print("\nStarting monitoring for the first token ID of the first market...")
            monitor = BookMonitor(token_id, args.output)
            monitor.run()
        else:
            logger.error("No valid token ID found to monitor.")
            return 1
    else:
        logger.error("No markets found for this event.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
