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

# Define the maximum depth of the order book to process
MAX_ORDERBOOK_DEPTH = 5

# Define the maximum depth of bids and asks to display
MAX_DISPLAY_DEPTH = 5


class MultiEventMonitor:
    """Monitor orderbook updates for multiple event slugs simultaneously."""

    def __init__(
        self,
        event_slugs: list[str],
        output_file: str = "bids_0999.csv",
        ws_url: Optional[str] = None,
        check_interval: int = 60,
        ticker_change_file: str = "ticker_changes.csv",
    ):
        """
        Initialize the multi-event monitor.

        Args:
            event_slugs: List of event slugs to monitor
            output_file: CSV file to save bid data
            ws_url: Optional WebSocket URL override
            check_interval: How often to check if markets are still active (seconds)
            ticker_change_file: CSV file to save ticker change events
        """
        self.event_slugs = event_slugs
        self.output_file = output_file
        self.ws_url = ws_url or WS_URL
        self.check_interval = check_interval
        self.ticker_change_file = ticker_change_file
        
        # Track token IDs and market status
        self.token_ids: dict[str, list[str]] = {}  # slug -> [token_ids]
        self.market_active: dict[str, bool] = {}  # slug -> is_active
        self.slug_by_token: dict[str, str] = {}  # token_id -> slug
        
        # Track bid/ask data
        self.previous_sizes = {}  # Track previous sizes at each price level and side
        
        # CSV file handles
        self.csv_file = None
        self.csv_writer = None
        
        # Ticker change CSV file handles
        self.ticker_csv_file = None
        self.ticker_csv_writer = None
        
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
        
        # Setup ticker change CSV
        self.ticker_csv_file = open(self.ticker_change_file, "a", newline="")
        self.ticker_csv_writer = csv.writer(self.ticker_csv_file)
        
        # Check if the file is empty to write headers
        if self.ticker_csv_file.tell() == 0:
            self.ticker_csv_writer.writerow([
                "timestamp_ms",
                "timestamp_iso",
                "timestamp_est",
                "event_type",
                "asset_id",
                "event_slug",
                "raw_data"
            ])
            self.ticker_csv_file.flush()
        logger.info("Ticker change CSV initialized (append mode): %s", self.ticker_change_file)

    def close_csv(self):
        """Close CSV files."""
        if self.csv_file:
            self.csv_file.close()
        if self.ticker_csv_file:
            self.ticker_csv_file.close()

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
            data: WebSocket message data with format:
                {
                  "event_type": "book",
                  "asset_id": "...",
                  "market": "...",
                  "bids": [{"price": ".48", "size": "30"}, ...],
                  "asks": [{"price": ".52", "size": "25"}, ...],
                  "timestamp": "123456789000"
                }
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

        # Extract basic info
        timestamp_ms = data.get("timestamp", int(datetime.utcnow().timestamp() * 1000))
        
        # Extract bids and asks arrays
        bids = data.get("bids", [])[:MAX_ORDERBOOK_DEPTH]  # Limit to top N bids
        asks = data.get("asks", [])[:MAX_ORDERBOOK_DEPTH]  # Limit to top N asks
        
        # Calculate best_bid and best_ask
        best_bid = bids[0]["price"] if bids else "N/A"
        best_ask = asks[0]["price"] if asks else "N/A"
        
        # Process bids at target price
        for bid in bids:
            try:
                price = float(bid.get("price", 0))
                size = float(bid.get("size", 0))
                
                # Check if this bid is at our target price
                if abs(price - TARGET_PRICE) < 0.0001:
                    side = "BID"
                    
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
                logger.error("Error processing bid: %s", e)
                continue
        
        # Process asks at target price
        for ask in asks:
            try:
                price = float(ask.get("price", 0))
                size = float(ask.get("size", 0))
                
                # Check if this ask is at our target price
                if abs(price - TARGET_PRICE) < 0.0001:
                    side = "ASK"
                    
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
                logger.error("Error processing ask: %s", e)
                continue
        
        # Limit the depth of bids and asks for display
        bids_display = sorted(data.get("bids", []), key=lambda x: float(x["price"]), reverse=True)[:MAX_DISPLAY_DEPTH]
        asks_display = sorted(data.get("asks", []), key=lambda x: float(x["price"]))[:MAX_DISPLAY_DEPTH]

        # Print the 5 highest bids and 5 lowest asks as strings in the desired format
        print(f"Top 5 Bids: {[f'price: {bid['price']}, size: {bid['size']}' for bid in bids_display]}")
        print(f"Top 5 Asks: {[f'price: {ask['price']}, size: {ask['size']}' for ask in asks_display]}")

    def process_ticker_change(self, data: dict[str, Any]):
        """
        Process a tick_size_change event.
        
        Args:
            data: WebSocket message data for tick_size_change event
        """
        if not isinstance(data, dict):
            logger.debug("Unexpected ticker change message format: %s", data)
            return
        
        # Extract asset ID to determine which market this is for
        asset_id = data.get("asset_id")
        if not asset_id:
            logger.debug("No asset_id in ticker change message")
            return
        
        # Look up the slug for this token
        slug = self.slug_by_token.get(asset_id)
        if not slug:
            logger.debug("Unknown asset_id in ticker change: %s", asset_id)
            return
        
        # Get current time for timestamp calculations
        now = datetime.utcnow()
        
        # Extract timestamp from data or use current time
        timestamp_ms = data.get("timestamp", int(now.timestamp() * 1000))
        
        # Create ISO timestamp
        timestamp_iso = now.isoformat() + "Z"
        
        # Convert timestamp to EST
        est_timezone = pytz_timezone("US/Eastern")
        timestamp_est = now.astimezone(est_timezone).isoformat()
        
        # Get event type
        event_type = data.get("event_type", "tick_size_change")
        
        # Log to console
        logger.info(
            "[%s] Ticker change event for %s (slug: %s)",
            timestamp_iso,
            asset_id,
            slug,
        )
        
        # Write to ticker change CSV
        if self.ticker_csv_writer:
            self.ticker_csv_writer.writerow([
                timestamp_ms,
                timestamp_iso,
                timestamp_est,
                event_type,
                asset_id,
                slug,
                json.dumps(data)  # Save full raw data for analysis
            ])
            self.ticker_csv_file.flush()
            logger.debug("Ticker change event saved to %s", self.ticker_change_file)

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
                                print(f"Detected Event Type: {msg_type} (Book Event)")
                                self.process_book_update(data)

                            # Handle tick_size_change event
                            if msg_type == "tick_size_change":
                                print(f"Tick Size Change Event Detected: {data}")  # Print the tick size change message
                                self.process_ticker_change(data)

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
