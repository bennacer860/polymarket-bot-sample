"""Utilities for 15-minute crypto markets."""

import time
from typing import Literal

from ..logging_config import get_logger

logger = get_logger(__name__)

# Market ID prefixes for different crypto assets
MARKET_IDS = {
    "BTC": "btc-15m",
    "ETH": "eth-15m",
    "SOL": "sol-15m",
    "XRP": "xrp-15m",
}

MarketSelection = Literal["BTC", "ETH", "SOL", "XRP"]


def get_current_15m_utc() -> int:
    """
    Get current 15-minute UTC timestamp block.
    
    Returns:
        Unix timestamp rounded down to the nearest 15-minute interval.
    """
    now = int(time.time())
    FIFTEEN_MIN = 15 * 60
    return (now // FIFTEEN_MIN) * FIFTEEN_MIN


def get_market_slug(market_selection: MarketSelection, timestamp: int | None = None) -> str:
    """
    Get market slug for a 15-minute period.
    
    Args:
        market_selection: Crypto asset to trade (BTC, ETH, SOL, XRP)
        timestamp: Optional timestamp (if None, uses current 15m block)
        
    Returns:
        Market slug in format: "{market_base}-{timestamp}"
        Example: "btc-15m-1707523200"
    """
    market_base = MARKET_IDS.get(market_selection)
    if not market_base:
        logger.error("Invalid market selection: %s", market_selection)
        raise ValueError(f"Invalid market selection: {market_selection}")
    
    if timestamp is None:
        timestamp = get_current_15m_utc()
    
    slug = f"{market_base}-{timestamp}"
    logger.debug("Generated market slug: %s", slug)
    return slug
