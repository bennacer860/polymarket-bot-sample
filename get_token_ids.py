#!/usr/bin/env python3
"""
Helper script to find token IDs for a Polymarket event slug.
This makes it easier to get the token_id needed for monitor_book_bids.py
"""

import argparse
import sys

from src.gamma_client import fetch_event_by_slug
from src.logging_config import setup_logging, get_logger

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
        
        # Get tokens
        tokens = market.get("tokens", [])
        if tokens:
            print(f"  Tokens:")
            for token in tokens:
                outcome = token.get("outcome", "Unknown")
                token_id = token.get("token_id", "N/A")
                print(f"    - {outcome}: {token_id}")
        else:
            print(f"  No tokens found")
        print()
    
    # Give usage example
    if markets and markets[0].get("tokens"):
        token_id = markets[0]["tokens"][0].get("token_id")
        print("\nExample usage:")
        print(f"  python monitor_book_bids.py --token-id {token_id}")
        print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
