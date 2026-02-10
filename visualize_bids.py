#!/usr/bin/env python3
"""
Simple visualization script for bid data collected by monitor_book_bids.py

Requires: pandas, matplotlib
Install with: pip install pandas matplotlib
"""

import argparse
import sys
from pathlib import Path

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    print("Error: This script requires pandas and matplotlib")
    print("Install with: pip install pandas matplotlib")
    sys.exit(1)


def visualize_bids(csv_file: str, output_prefix: str = "bid_analysis"):
    """
    Create visualizations from bid data CSV.
    
    Args:
        csv_file: Path to the CSV file from monitor_book_bids.py
        output_prefix: Prefix for output image files
    """
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"Error: File not found: {csv_file}")
        return False
    
    # Load data
    try:
        df = pd.read_csv(csv_file)
        print(f"Loaded {len(df)} records from {csv_file}")
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return False
    
    # Check if we have data
    if len(df) == 0:
        print("No data to visualize")
        return False
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp_iso'])
    
    # Sort by timestamp
    df = df.sort_values('timestamp')
    
    # Create visualizations
    print("\nGenerating visualizations...")
    
    # 1. Total bid size over time
    plt.figure(figsize=(14, 6))
    plt.plot(df['timestamp'], df['size'], marker='o', linewidth=2, markersize=4)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Total Bid Size at 0.999', fontsize=12)
    plt.title('Total Bid Size at 0.999 Price Level Over Time', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # Format x-axis to show time nicely
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    
    plt.tight_layout()
    output_file = f"{output_prefix}_total_size.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")
    plt.close()
    
    # 2. New bid activity (size changes)
    plt.figure(figsize=(14, 6))
    colors = ['green' if x > 0 else 'red' for x in df['size_change']]
    plt.bar(df['timestamp'], df['size_change'], color=colors, alpha=0.7, width=0.001)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Size Change (New Bids)', fontsize=12)
    plt.title('New Bid Activity at 0.999 Price Level', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='y')
    plt.xticks(rotation=45)
    
    # Format x-axis
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    
    plt.tight_layout()
    output_file = f"{output_prefix}_new_bids.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")
    plt.close()
    
    # 3. Cumulative bid count (how many bid events)
    plt.figure(figsize=(14, 6))
    df['bid_count'] = range(1, len(df) + 1)
    plt.plot(df['timestamp'], df['bid_count'], marker='o', linewidth=2, markersize=4, color='purple')
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Cumulative Number of Bid Events', fontsize=12)
    plt.title('Cumulative Bid Events at 0.999 Price Level', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # Format x-axis
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    
    plt.tight_layout()
    output_file = f"{output_prefix}_cumulative.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")
    plt.close()
    
    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)
    print(f"Total bid events: {len(df)}")
    print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Duration: {df['timestamp'].max() - df['timestamp'].min()}")
    print(f"\nBid Size:")
    print(f"  Min: {df['size'].min():.2f}")
    print(f"  Max: {df['size'].max():.2f}")
    print(f"  Mean: {df['size'].mean():.2f}")
    print(f"  Final: {df['size'].iloc[-1]:.2f}")
    print(f"\nSize Changes:")
    print(f"  Total increase: {df['size_change'].sum():.2f}")
    print(f"  Average per event: {df['size_change'].mean():.2f}")
    print(f"  Largest single increase: {df['size_change'].max():.2f}")
    print("=" * 60)
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Visualize bid data from monitor_book_bids.py"
    )
    parser.add_argument(
        "csv_file",
        help="CSV file from monitor_book_bids.py (default: bids_0999.csv)",
        nargs="?",
        default="bids_0999.csv"
    )
    parser.add_argument(
        "--output",
        default="bid_analysis",
        help="Output file prefix for generated images (default: bid_analysis)"
    )
    
    args = parser.parse_args()
    
    success = visualize_bids(args.csv_file, args.output)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
