#!/usr/bin/env python3
"""
Example usage of the multi-event monitoring features.

This script demonstrates how to use the monitoring APIs programmatically.
"""

import asyncio
from src.markets.fifteen_min import get_market_slug, get_current_15m_utc
from src.monitors.multi_event_monitor import MultiEventMonitor
from src.monitors.continuous_15min_monitor import ContinuousFifteenMinMonitor
from src.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


async def example_multi_event_monitor():
    """Example: Monitor multiple specific event slugs."""
    setup_logging()
    
    logger.info("Example: Multi-Event Monitor")
    logger.info("=" * 60)
    
    # Define event slugs to monitor
    # Replace these with real event slugs from Polymarket
    event_slugs = [
        "btc-15m-1707523200",
        "eth-15m-1707523200",
    ]
    
    logger.info("Monitoring events: %s", ", ".join(event_slugs))
    
    # Create and run monitor
    monitor = MultiEventMonitor(
        event_slugs=event_slugs,
        output_file="example_multi_bids.csv",
    )
    
    # Run the monitor (will exit when all markets end)
    await monitor.run()
    
    logger.info("Multi-event monitor completed")


async def example_continuous_15min_monitor():
    """Example: Continuously monitor current 15-minute markets."""
    setup_logging()
    
    logger.info("Example: Continuous 15-Minute Monitor")
    logger.info("=" * 60)
    
    # Monitor BTC and ETH 15-minute markets
    markets = ["BTC", "ETH"]
    
    logger.info("Monitoring continuous 15-minute markets: %s", ", ".join(markets))
    
    # Create and run monitor
    monitor = ContinuousFifteenMinMonitor(
        market_selections=markets,
        output_file="example_15min_bids.csv",
    )
    
    # Run the monitor (will continue indefinitely)
    await monitor.run()


def example_slug_generation():
    """Example: Generate market slugs for 15-minute periods."""
    setup_logging()
    
    logger.info("Example: 15-Minute Market Slug Generation")
    logger.info("=" * 60)
    
    # Get current 15-minute timestamp
    current_ts = get_current_15m_utc()
    logger.info("Current 15-minute block timestamp: %d", current_ts)
    
    # Generate slugs for different markets
    markets = ["BTC", "ETH", "SOL", "XRP"]
    
    logger.info("\nCurrent market slugs:")
    for market in markets:
        slug = get_market_slug(market, current_ts)
        logger.info("  %s: %s", market, slug)
    
    # Generate slug for a specific timestamp
    specific_ts = 1707523200  # 2024-02-10 00:00:00 UTC
    logger.info("\nMarket slugs for timestamp %d:", specific_ts)
    for market in markets:
        slug = get_market_slug(market, specific_ts)
        logger.info("  %s: %s", market, slug)


def main():
    """Run examples."""
    print("\n" + "=" * 60)
    print("Multi-Event Monitoring Examples")
    print("=" * 60 + "\n")
    
    # Example 1: Slug generation (synchronous)
    example_slug_generation()
    
    print("\n" + "=" * 60)
    print("\nTo run the async examples, uncomment the code below:")
    print("  1. Multi-event monitor (monitors specific slugs)")
    print("  2. Continuous 15-min monitor (monitors current markets)")
    print("\nNote: These require valid market slugs and will run until")
    print("markets end (multi-event) or indefinitely (continuous).")
    print("=" * 60 + "\n")
    
    # Uncomment to run async examples:
    # asyncio.run(example_multi_event_monitor())
    # asyncio.run(example_continuous_15min_monitor())


if __name__ == "__main__":
    main()
