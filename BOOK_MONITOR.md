# Book Monitor - 0.999 Price Bid Tracking

This directory contains scripts to monitor Polymarket CLOB WebSocket for bids at the 0.999 price level.

## Quick Start

### 1. Find Token ID

```bash
python get_token_ids.py --slug your-event-slug
```

Example output:
```
Event: BTC 15-min Up/Down
Slug: btc-15m-20250209-1200

Found 1 market(s):

Market 1:
  Question: Will BTC go up or down in the next 15 minutes?
  Closed: False
  Tokens:
    - Up: 0x123abc...
    - Down: 0x456def...

Example usage:
  python monitor_book_bids.py --token-id 0x123abc...
```

### 2. Monitor Orderbook

```bash
python monitor_book_bids.py --token-id <token-id>
```

The script will:
- Connect to the Polymarket CLOB WebSocket
- Subscribe to orderbook updates for the token
- Log every new bid at 0.999 price
- Save data to `bids_0999.csv`

Output:
```
Connecting to wss://ws-subscriptions-clob.polymarket.com/ws/market
Monitoring token: 0x123abc...
Target price: 0.999
------------------------------------------------------------
CSV output initialized: bids_0999.csv
Subscribed to book updates for 0x123abc...

[2026-02-09T01:23:45.678Z] New bid at 0.999
  Size: 150.00 (change: +150.00)
  Token: 0x123abc...

[2026-02-09T01:24:12.345Z] New bid at 0.999
  Size: 275.00 (change: +125.00)
  Token: 0x123abc...
```

### 3. Analyze Data

The CSV file contains:
- `timestamp_ms`: Unix timestamp in milliseconds (for precise timing analysis)
- `timestamp_iso`: Human-readable timestamp (e.g., 2026-02-09T01:23:45.678Z)
- `price`: Bid price (0.999)
- `size`: Total size of bids at this price level
- `size_change`: Increase in size from previous update
- `token_id`: Token being monitored

Example CSV:
```csv
timestamp_ms,timestamp_iso,price,size,size_change,token_id
1739060625678,2026-02-09T01:23:45.678Z,0.999,150.0,150.0,0x123abc...
1739060652345,2026-02-09T01:24:12.345Z,0.999,275.0,125.0,0x123abc...
```

## Visualization

You can visualize the data using:

### Python (pandas + matplotlib)

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('bids_0999.csv')
df['timestamp'] = pd.to_datetime(df['timestamp_iso'])

# Plot size over time
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp'], df['size'])
plt.xlabel('Time')
plt.ylabel('Total Bid Size at 0.999')
plt.title('Bid Size at 0.999 Over Time')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# Plot new bids (size changes)
plt.figure(figsize=(12, 6))
plt.bar(df['timestamp'], df['size_change'])
plt.xlabel('Time')
plt.ylabel('New Bid Size')
plt.title('New Bids at 0.999 Over Time')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### Excel

1. Open `bids_0999.csv` in Excel
2. Select the data
3. Insert > Chart > Line Chart or Scatter Chart
4. Use `timestamp_iso` for X-axis and `size` or `size_change` for Y-axis

## WebSocket Configuration

If the default WebSocket URL doesn't work, you can specify a custom one:

```bash
python monitor_book_bids.py --token-id <token-id> --ws-url wss://custom-url.com/ws
```

Common Polymarket WebSocket URLs:
- `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- `wss://clob.polymarket.com/ws`

## Troubleshooting

### Connection Issues

If you get WebSocket connection errors:
1. Verify the WebSocket URL is correct
2. Check if Polymarket's WebSocket API is available
3. Ensure your network allows WebSocket connections

### No Data

If connected but no bids are logged:
1. Verify the token_id is correct
2. Check that there's active trading on this market
3. Bids may not be placed at exactly 0.999 - check orderbook manually

### Message Format

If the script isn't detecting bids, the WebSocket message format may have changed. Check the raw messages and update the `process_book_update` method in `monitor_book_bids.py` to match the actual format.
