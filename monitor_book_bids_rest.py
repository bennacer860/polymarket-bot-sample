#!/usr/bin/env python3
"""
Alternative implementation using REST API polling instead of WebSocket.
This is simpler but less efficient than the WebSocket approach.

Use this if you have trouble with the WebSocket connection.
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pytz import timezone

from py_clob_client.client import ClobClient

# Target price level to monitor
TARGET_PRICE = 0.999

# Polling interval in seconds
POLL_INTERVAL = 1.0


class RestBookMonitor:
    """Monitor orderbook via REST API polling."""

    def __init__(
        self,
        token_id: str,
        output_file: str = "bids_0999.csv",
        interval: float = POLL_INTERVAL,
    ):
        """
        Initialize the REST book monitor.

        Args:
            token_id: The token ID to monitor
            output_file: CSV file to save bid data
            interval: Polling interval in seconds
        """
        self.token_id = token_id
        self.output_file = output_file
        self.interval = interval
        self.previous_size = 0.0
        self.csv_file = None
        self.csv_writer = None
        self.client = ClobClient("https://clob.polymarket.com")

    def setup_csv(self):
        """Setup CSV file with headers."""
        self.csv_file = open(self.output_file, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        # Write headers
        self.csv_writer.writerow([
            "timestamp_ms",
            "timestamp_iso",
            "timestamp_est",
            "price",
            "size",
            "size_change",
            "best_bid",
            "best_ask",
            "token_id"
        ])
        self.csv_file.flush()
        print(f"CSV output initialized: {self.output_file}")

    def close_csv(self):
        """Close CSV file."""
        if self.csv_file:
            self.csv_file.close()

    def check_book(self):
        """Check orderbook for 0.999 bids."""
        try:
            book = self.client.get_order_book(self.token_id)
            
            if not book or not book.bids:
                return
            
            # Get best bid and best ask
            best_bid = float(book.bids[0].price) if book.bids else 0.0
            best_ask = float(book.asks[0].price) if book.asks else 0.0
            
            # Find bids at target price
            total_size = 0.0
            for bid in book.bids:
                price = float(bid.price)
                if abs(price - TARGET_PRICE) < 0.0001:
                    total_size += float(bid.size)
            
            # Check if size increased
            if total_size > self.previous_size:
                size_change = total_size - self.previous_size
                
                # Get current timestamp
                now = datetime.utcnow()
                timestamp_ms = int(now.timestamp() * 1000)
                timestamp_iso = now.isoformat() + "Z"
                
                # Convert timestamp to EST
                est_timezone = timezone("US/Eastern")
                timestamp_est = now.astimezone(est_timezone).isoformat()
                
                # Log to console
                print(f"\n[{timestamp_iso}] New bid at {TARGET_PRICE}")
                print(f"  Size: {total_size:.2f} (change: +{size_change:.2f})")
                print(f"  Token: {self.token_id}")
                print(f"  Best Bid: {best_bid}")
                print(f"  Best Ask: {best_ask}")
                
                # Write to CSV
                if self.csv_writer:
                    self.csv_writer.writerow([
                        timestamp_ms,
                        timestamp_iso,
                        timestamp_est,
                        TARGET_PRICE,
                        total_size,
                        size_change,
                        best_bid,
                        best_ask,
                        self.token_id
                    ])
                    self.csv_file.flush()
            
            # Update previous size
            if total_size > 0:
                self.previous_size = total_size
                
        except Exception as e:
            print(f"Error fetching orderbook: {e}")

    def run(self):
        """Run the monitor with polling."""
        print("REST API Orderbook Monitor")
        print(f"Token: {self.token_id}")
        print(f"Target price: {TARGET_PRICE}")
        print(f"Polling interval: {self.interval}s")
        print("-" * 60)
        
        self.setup_csv()
        
        try:
            while True:
                self.check_book()
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        finally:
            self.close_csv()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor Polymarket orderbook via REST API for 0.999 price bids"
    )
    parser.add_argument(
        "--token-id",
        required=True,
        help="Token ID to monitor"
    )
    parser.add_argument(
        "--output",
        default="bids_0999.csv",
        help="Output CSV file (default: bids_0999.csv)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {POLL_INTERVAL})"
    )
    
    args = parser.parse_args()
    
    monitor = RestBookMonitor(args.token_id, args.output, args.interval)
    monitor.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
