"""Multi-event WebSocket monitor for Polymarket markets."""

import asyncio
import csv
import json
from datetime import datetime
from typing import Any, Optional
from pytz import timezone as pytz_timezone

import websockets

from ..config import GAMMA_API
from ..gamma_client import fetch_event_by_slug, get_market_token_ids, is_market_ended
from ..logging_config import get_logger

logger = get_logger(__name__)

# WebSocket endpoint for Polymarket CLOB
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Target price level to monitor
TARGET_PRICE = 0.999


class MultiEventMonitor:
    """Monitor orderbook updates for multiple event slugs simultaneously."""

    def __init__(
        self,
        event_slugs: list[str],
        output_file: str = "bids_0999.csv",
        ws_url: Optional[str] = None,
        check_interval: int = 60,
    ):
        """
        Initialize the multi-event monitor.

        Args:
            event_slugs: List of event slugs to monitor
            output_file: CSV file to save bid data
            ws_url: Optional WebSocket URL override
            check_interval: How often to check if markets are still active (seconds)
        """
        self.event_slugs = event_slugs
        self.output_file = output_file
        self.ws_url = ws_url or WS_URL
        self.check_interval = check_interval
        
        # Track token IDs and market status
        self.token_ids: dict[str, list[str]] = {}  # slug -> [token_ids]
        self.market_active: dict[str, bool] = {}  # slug -> is_active
        self.slug_by_token: dict[str, str] = {}  # token_id -> slug
        
        # Track bid/ask data
        self.previous_sizes = {}  # Track previous sizes at each price level and side
        
        # CSV file handles
        self.csv_file = None
        self.csv_writer = None
        
        # WebSocket connection
        self.websocket = None
        self.running = False

    def setup_csv(self):
        """Setup CSV file with headers."""
        self.csv_file = open(self.output_file, "a", newline="")
        self.csv_writer = csv.writer(self.csv_file)

        # Check if the file is empty to write headers
        if self.csv_file.tell() == 0:
            self.csv_writer.writerow([
                "timestamp_ms",
                "timestamp_iso",
                "timestamp_est",
                "price",
                "size",
                "size_change",
                "side",
                "best_bid",
                "best_ask",
                "token_id",
                "event_slug"
            ])
            self.csv_file.flush()
        logger.info("CSV output initialized (append mode): %s", self.output_file)

    def close_csv(self):
        """Close CSV file."""
        if self.csv_file:
            self.csv_file.close()

    async def fetch_token_ids_for_slug(self, slug: str) -> list[str]:
        """
        Get CLOB token IDs for a market slug.
        
        Args:
            slug: Event slug
            
        Returns:
            List of token IDs for the market
        """
        try:
            event = fetch_event_by_slug(slug)
            if not event:
                logger.error("Failed to fetch event for slug: %s", slug)
                return []
            
            markets = event.get("markets", [])
            if not markets:
                logger.error("No markets found for slug: %s", slug)
                return []
            
            # Get token IDs from the first market
            market = markets[0]
            token_ids = get_market_token_ids(market)
            
            if not token_ids:
                logger.error("No token IDs found for slug: %s", slug)
                return []
            
            logger.info("Found %d token IDs for slug %s: %s", len(token_ids), slug, token_ids)
            return token_ids
            
        except Exception as e:
            logger.error("Error fetching token IDs for slug %s: %s", slug, e)
            return []

    async def initialize_markets(self):
        """Initialize all markets by fetching their token IDs."""
        logger.info("Initializing %d markets...", len(self.event_slugs))
        
        for slug in self.event_slugs:
            token_ids = await self.fetch_token_ids_for_slug(slug)
            if token_ids:
                self.token_ids[slug] = token_ids
                self.market_active[slug] = True
                
                # Map token IDs to slugs for reverse lookup
                for token_id in token_ids:
                    self.slug_by_token[token_id] = slug
                    
                logger.info("Initialized market: %s (active)", slug)
            else:
                logger.warning("Failed to initialize market: %s", slug)
                self.market_active[slug] = False
        
        # Check if any markets were successfully initialized
        active_count = sum(1 for active in self.market_active.values() if active)
        if active_count == 0:
            logger.error("No markets successfully initialized. Cannot start monitoring.")
            return False
        
        logger.info("Successfully initialized %d/%d markets", active_count, len(self.event_slugs))
        return True

    async def check_market_status(self):
        """Periodically check if markets are still active and close websocket if all ended."""
        while self.running:
            await asyncio.sleep(self.check_interval)
            
            logger.debug("Checking market status for %d markets", len(self.event_slugs))
            
            for slug in self.event_slugs:
                if not self.market_active.get(slug, False):
                    continue  # Skip already inactive markets
                
                try:
                    event = fetch_event_by_slug(slug)
                    if not event:
                        logger.warning("Failed to fetch event for status check: %s", slug)
                        continue
                    
                    markets = event.get("markets", [])
                    if not markets:
                        logger.warning("No markets found for status check: %s", slug)
                        continue
                    
                    market = markets[0]
                    if is_market_ended(market):
                        logger.info("Market %s has ended. Marking as inactive.", slug)
                        self.market_active[slug] = False
                        
                except Exception as e:
                    logger.error("Error checking market status for %s: %s", slug, e)
            
            # Check if all markets are inactive
            active_count = sum(1 for active in self.market_active.values() if active)
            if active_count == 0:
                logger.info("All markets have ended. Closing WebSocket connection.")
                self.running = False
                if self.websocket:
                    await self.websocket.close()
                break
            else:
                logger.debug("%d/%d markets still active", active_count, len(self.event_slugs))

    def process_book_update(self, data: dict[str, Any]):
        """
        Process a book update message.

        Args:
            data: WebSocket message data
        """
        if not isinstance(data, dict):
            logger.debug("Unexpected message format: %s", data)
            return

        # Extract asset ID to determine which market this is for
        asset_id = data.get("asset_id")
        if not asset_id:
            logger.debug("No asset_id in message")
            return
        
        # Look up the slug for this token
        slug = self.slug_by_token.get(asset_id)
        if not slug:
            logger.debug("Unknown asset_id: %s", asset_id)
            return
        
        # Check if this market is still active
        if not self.market_active.get(slug, False):
            logger.debug("Ignoring update for inactive market: %s", slug)
            return

        # Extract price changes from the update
        price_changes = data.get("price_changes", [])
        timestamp_ms = data.get("timestamp", int(datetime.utcnow().timestamp() * 1000))

        # Process each price change
        for change in price_changes:
            try:
                price = float(change.get("price", 0))
                size = float(change.get("size", 0))
                best_bid = change.get("best_bid", "N/A")
                best_ask = change.get("best_ask", "N/A")

                # Check if the best bid or ask is at our target price
                if best_bid == str(TARGET_PRICE) or best_ask == str(TARGET_PRICE):
                    # Determine if this specific price level is a bid or ask
                    # Bids are at or below best_bid, asks are at or above best_ask
                    side = None
                    try:
                        best_bid_float = float(best_bid) if best_bid != "N/A" else None
                        best_ask_float = float(best_ask) if best_ask != "N/A" else None
                        
                        if best_bid_float and price <= best_bid_float:
                            side = "BID"
                        elif best_ask_float and price >= best_ask_float:
                            side = "ASK"
                        else:
                            # If we can't determine, check which target was hit
                            if best_bid == str(TARGET_PRICE):
                                side = "BID"
                            else:
                                side = "ASK"
                    except (ValueError, TypeError):
                        side = "UNKNOWN"

                    # Calculate size change from previous
                    cache_key = f"{asset_id}_{price}_{side}"
                    previous_size = self.previous_sizes.get(cache_key, 0.0)
                    size_change = size - previous_size

                    # Only log if this is a new entry or increased size
                    if size_change > 0:
                        # Get current timestamp with milliseconds
                        now = datetime.utcnow()
                        timestamp_iso = now.isoformat() + "Z"

                        # Convert timestamp to EST
                        est_timezone = pytz_timezone("US/Eastern")
                        timestamp_est = now.astimezone(est_timezone).isoformat()

                        # Log to console
                        logger.info(
                            "[%s] New %s at %.3f for %s (slug: %s): size=%.2f, change=+%.2f (best_bid=%s, best_ask=%s)",
                            timestamp_iso,
                            side,
                            price,
                            asset_id,
                            slug,
                            size,
                            size_change,
                            best_bid,
                            best_ask,
                        )

                        # Write to CSV
                        if self.csv_writer:
                            self.csv_writer.writerow([
                                timestamp_ms,
                                timestamp_iso,
                                timestamp_est,
                                price,
                                size,
                                size_change,
                                side,
                                best_bid,
                                best_ask,
                                asset_id,
                                slug
                            ])
                            self.csv_file.flush()

                    # Update previous size
                    self.previous_sizes[cache_key] = size

            except (ValueError, KeyError) as e:
                logger.error("Error processing price change: %s", e)
                continue

    async def subscribe_and_monitor(self):
        """Connect to WebSocket and monitor book updates for all markets."""
        logger.info("Connecting to %s", self.ws_url)
        logger.info("Monitoring %d event slugs", len(self.event_slugs))
        logger.info("Target price: %.3f", TARGET_PRICE)
        logger.info("-" * 60)

        self.setup_csv()

        # Initialize markets and fetch token IDs
        success = await self.initialize_markets()
        if not success:
            logger.error("Failed to initialize markets. Exiting.")
            return

        # Get all token IDs to subscribe to
        all_token_ids = []
        for token_ids in self.token_ids.values():
            all_token_ids.extend(token_ids)
        
        if not all_token_ids:
            logger.error("No token IDs to subscribe to. Exiting.")
            return

        logger.info("Subscribing to %d token IDs across %d markets", len(all_token_ids), len(self.token_ids))

        try:
            async with websockets.connect(self.ws_url) as websocket:
                self.websocket = websocket
                self.running = True
                
                # Subscribe to the book channel for all tokens
                subscribe_msg = {
                    "type": "subscribe",
                    "assets_ids": all_token_ids,
                    "custom_feature_enabled": False
                }
                logger.info("Subscription message: %s", json.dumps(subscribe_msg))
                await websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to book updates for %d tokens", len(all_token_ids))

                # Start market status checking task
                status_task = asyncio.create_task(self.check_market_status())

                # Listen for updates
                try:
                    async for message in websocket:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)

                            # Check if the message is a list (empty message)
                            if isinstance(data, list):
                                logger.debug("Received empty list message")
                                continue

                            # Check if this is a book update
                            msg_type = data.get("event_type", data.get("type", ""))

                            if msg_type in ["book"]:
                                self.process_book_update(data)

                        except json.JSONDecodeError:
                            logger.error("Failed to decode message: %s", message)
                        except Exception as e:
                            logger.error("Error processing message: %s", e)
                
                except asyncio.CancelledError:
                    logger.info("Monitoring cancelled")
                finally:
                    # Cancel status checking task
                    status_task.cancel()
                    try:
                        await status_task
                    except asyncio.CancelledError:
                        pass

        except websockets.exceptions.WebSocketException as e:
            logger.error("WebSocket error: %s", e)
        finally:
            self.running = False
            self.close_csv()

    async def run(self):
        """Run the monitor asynchronously."""
        try:
            await self.subscribe_and_monitor()
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.close_csv()

    def run_sync(self):
        """Run the monitor synchronously (blocking)."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.close_csv()
