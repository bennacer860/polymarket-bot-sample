#!/usr/bin/env python3
"""
Monitor Polymarket CLOB WebSocket for bids at 0.999 price level.

This script subscribes to the book channel for a specific token/market
and logs every update where a new bid is placed at the 0.999 price level.
Data is saved to CSV for visualization.
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from typing import Optional
from pytz import timezone

import websockets

# WebSocket endpoint for Polymarket CLOB
# Update this URL based on Polymarket's actual WebSocket endpoint
# Common patterns:
# - wss://ws-subscriptions-clob.polymarket.com/ws/market
# - wss://clob.polymarket.com/ws
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Target price level to monitor
TARGET_PRICE = 0.999


class BookMonitor:
    """Monitor orderbook updates for a specific price level."""

    def __init__(self, token_id: str, output_file: str = "bids_0999.csv", ws_url: Optional[str] = None):
        """
        Initialize the book monitor.

        Args:
            token_id: The token ID to monitor
            output_file: CSV file to save bid data
            ws_url: Optional WebSocket URL override
        """
        self.token_id = token_id
        self.output_file = output_file
        self.ws_url = ws_url or WS_URL
        self.previous_sizes = {}  # Track previous sizes at each price level and side
        self.csv_file = None
        self.csv_writer = None

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
        print(f"CSV output initialized (append mode): {self.output_file}")

    def close_csv(self):
        """Close CSV file."""
        if self.csv_file:
            self.csv_file.close()

    def process_book_update(self, data: dict):
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
        # Ensure the data is a dictionary
        if not isinstance(data, dict):
            print(f"Unexpected message format: {data}")
            return

        # Extract basic info
        timestamp_ms = data.get("timestamp", int(datetime.utcnow().timestamp() * 1000))
        event_slug = data.get("market", "unknown")
        
        # Extract bids and asks arrays
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
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
                    cache_key = f"{price}_{side}"
                    previous_size = self.previous_sizes.get(cache_key, 0.0)
                    size_change = size - previous_size
                    
                    # Only log if this is a new entry or increased size
                    if size_change > 0:
                        # Get current timestamp with milliseconds
                        now = datetime.utcnow()
                        timestamp_iso = now.isoformat() + "Z"
                        
                        # Convert timestamp to EST
                        est_timezone = timezone("US/Eastern")
                        timestamp_est = now.astimezone(est_timezone).isoformat()
                        
                        # Log to console
                        print(f"\n[{timestamp_iso}] New {side} at {price} (best_bid={best_bid}, best_ask={best_ask})")
                        print(f"  Size: {size:.2f} (change: +{size_change:.2f})")
                        print(f"  Token: {self.token_id}")
                        print(f"  Event Slug: {event_slug}")
                        print(f"  Best Bid: {best_bid}")
                        print(f"  Best Ask: {best_ask}")
                        
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
                                self.token_id,
                                event_slug
                            ])
                            self.csv_file.flush()
                    
                    # Update previous size
                    self.previous_sizes[cache_key] = size
                    
            except (ValueError, KeyError) as e:
                print(f"Error processing bid: {e}")
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
                    cache_key = f"{price}_{side}"
                    previous_size = self.previous_sizes.get(cache_key, 0.0)
                    size_change = size - previous_size
                    
                    # Only log if this is a new entry or increased size
                    if size_change > 0:
                        # Get current timestamp with milliseconds
                        now = datetime.utcnow()
                        timestamp_iso = now.isoformat() + "Z"
                        
                        # Convert timestamp to EST
                        est_timezone = timezone("US/Eastern")
                        timestamp_est = now.astimezone(est_timezone).isoformat()
                        
                        # Log to console
                        print(f"\n[{timestamp_iso}] New {side} at {price} (best_bid={best_bid}, best_ask={best_ask})")
                        print(f"  Size: {size:.2f} (change: +{size_change:.2f})")
                        print(f"  Token: {self.token_id}")
                        print(f"  Event Slug: {event_slug}")
                        print(f"  Best Bid: {best_bid}")
                        print(f"  Best Ask: {best_ask}")
                        
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
                                self.token_id,
                                event_slug
                            ])
                            self.csv_file.flush()
                    
                    # Update previous size
                    self.previous_sizes[cache_key] = size
                    
            except (ValueError, KeyError) as e:
                print(f"Error processing ask: {e}")
                continue

    async def subscribe_and_monitor(self):
        """Connect to WebSocket and monitor book updates."""
        print(f"Connecting to {self.ws_url}")
        print(f"Monitoring token: {self.token_id}")
        print(f"Target price: {TARGET_PRICE}")
        print("-" * 60)

        self.setup_csv()

        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Subscribe to the book channel
                subscribe_msg = {
                    "type": "subscribe",
                    "assets_ids": [self.token_id],
                    "custom_feature_enabled": False
                }
                print(f"Subscription message: {json.dumps(subscribe_msg)}")
                await websocket.send(json.dumps(subscribe_msg))
                print(f"Subscribed to book updates for {self.token_id}")

                # Listen for updates
                async for message in websocket:
                    try:
                        print(f"Received message: {message}")  # Log the raw message
                        data = json.loads(message)

                        # Check if the message is a list
                        if isinstance(data, list):
                            print("Received an empty list or unexpected list message. Skipping.")
                            continue

                        # Check if this is a book update
                        msg_type = data.get("event_type", data.get("type", ""))

                        if msg_type in ["book"]:
                            self.process_book_update(data)

                    except json.JSONDecodeError:
                        print(f"Failed to decode message: {message}")
                    except Exception as e:
                        print(f"Error processing message: {e}")

        except websockets.exceptions.WebSocketException as e:
            print(f"WebSocket error: {e}")
        finally:
            self.close_csv()

    def run(self):
        """Run the monitor."""
        try:
            asyncio.run(self.subscribe_and_monitor())
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        finally:
            self.close_csv()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor Polymarket CLOB WebSocket for 0.999 price bids"
    )
    parser.add_argument(
        "--token-id",
        required=True,
        help="Token ID to monitor (e.g., market token ID from Polymarket)"
    )
    parser.add_argument(
        "--output",
        default="bids_0999.csv",
        help="Output CSV file (default: bids_0999.csv)"
    )
    parser.add_argument(
        "--ws-url",
        help="WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)"
    )
    
    args = parser.parse_args()
    
    monitor = BookMonitor(args.token_id, args.output, args.ws_url)
    monitor.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
