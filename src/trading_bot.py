"""Trading bot for 15-min crypto Up/Down events."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from .config import (
    POLL_INTERVAL_SECONDS,
    POST_RESOLUTION_ORDER_PRICE,
    POST_RESOLUTION_ORDER_SIZE,
    RESOLUTION_BUFFER_SECONDS,
)
from .clob_client import place_limit_order
from .gamma_client import (
    fetch_event_by_slug,
    get_winning_token_id,
    is_market_ended,
)
from .logging_config import get_logger

logger = get_logger(__name__)


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime (UTC)."""
    if not s:
        return None
    try:
        # Handle optional 'Z' and fractional seconds
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _validate_15min_crypto_event(event: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate that the event is a 15-min crypto binary market.

    Returns (is_valid, error_message).
    """
    markets = event.get("markets") or []
    if len(markets) != 1:
        return False, f"Expected 1 market for 15-min crypto, got {len(markets)}"

    market = markets[0]
    if not market.get("automaticallyResolved"):
        return False, "Event is not automatically resolved (not a crypto market?)"

    outcomes = market.get("outcomes") or ""
    if isinstance(outcomes, list):
        outcomes = ",".join(outcomes)
    if "up" not in str(outcomes).lower() and "down" not in str(outcomes).lower():
        # Allow Yes/No as well for binary
        pass  # Still allow if it's binary
    return True, ""


async def run_bot(slug: str) -> bool:
    """
    Run the 15-min crypto trading bot for the given event slug.

    1. Fetch event and validate
    2. Wait until endDate + resolution buffer
    3. Poll until market is resolved
    4. Place limit order for 1 share @ 0.999 on winning side

    Returns True if order was placed (or attempted), False on validation/early exit.
    """
    logger.info("Starting trading bot for slug=%s", slug)

    event = fetch_event_by_slug(slug)
    if not event:
        logger.error("Cannot start bot: event not found")
        return False

    markets = event.get("markets") or []
    if len(markets) != 1:
        logger.error("Expected 1 market for 15-min crypto, got %d", len(markets))
        return False

    is_valid, err = _validate_15min_crypto_event(event)
    if not is_valid:
        logger.error("Invalid event: %s", err)
        return False

    market = markets[0]
    end_date_str = event.get("endDate") or market.get("endDate")
    end_dt = _parse_iso_date(end_date_str)
    if not end_dt:
        logger.error("Could not parse endDate: %s", end_date_str)
        return False

    # Ensure end_dt is timezone-aware
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    wait_until = end_dt.timestamp() + RESOLUTION_BUFFER_SECONDS
    seconds_to_wait = wait_until - now.timestamp()

    if seconds_to_wait > 0:
        logger.info(
            "Waiting %.1f seconds until endDate + %ds buffer (endDate=%s)",
            seconds_to_wait,
            RESOLUTION_BUFFER_SECONDS,
            end_date_str,
        )
        await asyncio.sleep(seconds_to_wait)
    else:
        logger.info("Event already past endDate, proceeding to poll for resolution")

    # Poll for resolution
    poll_count = 0
    while True:
        poll_count += 1
        event = fetch_event_by_slug(slug)
        if not event:
            logger.warning("Poll #%d: failed to fetch event, retrying...", poll_count)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        markets = event.get("markets") or []
        if not markets:
            logger.warning("Poll #%d: no markets in event, retrying...", poll_count)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        market = markets[0]
        if is_market_ended(market):
            logger.info("Poll #%d: market resolved (ended=%s, closed=%s)", poll_count, market.get("ended"), market.get("closed"))
            break

        logger.debug("Poll #%d: market not yet resolved, retrying in %ds", poll_count, POLL_INTERVAL_SECONDS)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    # Check acceptingOrders - market may have closed order book
    if not market.get("acceptingOrders", True):
        logger.warning("Market is no longer accepting orders. Order placement may fail.")

    winning_token = get_winning_token_id(market)
    if not winning_token:
        logger.error("Could not determine winning token from outcomePrices=%s", market.get("outcomePrices"))
        return False

    logger.info("Placing post-resolution order: 1 share @ %.3f on winning token %s", POST_RESOLUTION_ORDER_PRICE, winning_token)

    resp = place_limit_order(
        token_id=winning_token,
        price=POST_RESOLUTION_ORDER_PRICE,
        size=POST_RESOLUTION_ORDER_SIZE,
        side="BUY",
    )

    if resp is None:
        logger.error("Order placement failed (client error)")
        return False

    success = resp.get("success", False)
    if success:
        logger.info("Order placed successfully: orderId=%s, status=%s", resp.get("orderId"), resp.get("status"))
    else:
        logger.warning(
            "Order did not go through: errorMsg=%s, success=%s. Check logs for details.",
            resp.get("errorMsg"),
            success,
        )

    return True
