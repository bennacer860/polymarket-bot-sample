#!/usr/bin/env python3
"""
Simple data analyzer for bid data collected by monitor_book_bids.py
Shows key statistics without requiring visualization libraries.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


def analyze_bids(csv_file: str):
    """
    Analyze bid data and print statistics.
    
    Args:
        csv_file: Path to the CSV file from monitor_book_bids.py
    """
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"Error: File not found: {csv_file}")
        return False
    
    # Read CSV data
    rows = []
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    if not rows:
        print("No data found in CSV file")
        return False
    
    print("=" * 70)
    print("BID ANALYSIS - 0.999 PRICE LEVEL")
    print("=" * 70)
    
    # Basic stats
    print(f"\nData file: {csv_file}")
    print(f"Total bid events: {len(rows)}")
    
    # Time analysis
    first_timestamp = datetime.fromisoformat(rows[0]['timestamp_iso'].replace('Z', '+00:00'))
    last_timestamp = datetime.fromisoformat(rows[-1]['timestamp_iso'].replace('Z', '+00:00'))
    duration = last_timestamp - first_timestamp
    
    print(f"\nTime Range:")
    print(f"  First bid: {first_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
    print(f"  Last bid:  {last_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
    print(f"  Duration:  {duration}")
    
    # Convert to numeric for analysis
    sizes = [float(row['size']) for row in rows]
    changes = [float(row['size_change']) for row in rows]
    
    # Size analysis
    print(f"\nBid Size at 0.999:")
    print(f"  Initial:  {sizes[0]:,.2f} shares")
    print(f"  Final:    {sizes[-1]:,.2f} shares")
    print(f"  Minimum:  {min(sizes):,.2f} shares")
    print(f"  Maximum:  {max(sizes):,.2f} shares")
    print(f"  Average:  {sum(sizes)/len(sizes):,.2f} shares")
    
    # Change analysis
    print(f"\nBid Changes:")
    print(f"  Total increase:      {sum(changes):,.2f} shares")
    print(f"  Average per event:   {sum(changes)/len(changes):,.2f} shares")
    print(f"  Largest increase:    {max(changes):,.2f} shares")
    print(f"  Smallest increase:   {min(changes):,.2f} shares")
    
    # Frequency analysis
    if duration.total_seconds() > 0:
        events_per_minute = len(rows) / (duration.total_seconds() / 60)
        print(f"\nFrequency:")
        print(f"  Events per minute:   {events_per_minute:.2f}")
        print(f"  Average time between events: {duration.total_seconds()/len(rows):.2f} seconds")
    
    # Find periods of high activity
    print(f"\nTop 5 Largest Bid Increases:")
    sorted_rows = sorted(rows, key=lambda x: float(x['size_change']), reverse=True)
    for i, row in enumerate(sorted_rows[:5], 1):
        ts = datetime.fromisoformat(row['timestamp_iso'].replace('Z', '+00:00'))
        print(f"  {i}. {ts.strftime('%H:%M:%S.%f')[:-3]}: +{float(row['size_change']):,.2f} shares")
    
    # Token info
    print(f"\nToken ID: {rows[0]['token_id']}")
    
    print("=" * 70)
    
    # Recommendations
    print("\nNext Steps:")
    print("  1. Visualize this data: python visualize_bids.py", csv_file)
    print("  2. Compare with market events/prices at these times")
    print("  3. Look for patterns before event resolution")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze bid data from monitor_book_bids.py"
    )
    parser.add_argument(
        "csv_file",
        help="CSV file from monitor_book_bids.py (default: bids_0999.csv)",
        nargs="?",
        default="bids_0999.csv"
    )
    
    args = parser.parse_args()
    
    success = analyze_bids(args.csv_file)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
