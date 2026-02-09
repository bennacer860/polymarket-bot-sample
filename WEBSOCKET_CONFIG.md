# WebSocket Configuration Guide

This document provides guidance on configuring the WebSocket connection for the Polymarket CLOB book monitor.

## Finding the WebSocket URL

The WebSocket URL for Polymarket's CLOB may change over time. Here's how to find the correct endpoint:

### Option 1: Check Polymarket Documentation

Visit the official Polymarket developer documentation:
- https://docs.polymarket.com

Look for WebSocket or real-time data sections.

### Option 2: Inspect the Web Interface

1. Open https://polymarket.com in your browser
2. Open Developer Tools (F12)
3. Go to the Network tab
4. Filter by "WS" (WebSocket)
5. Look for active WebSocket connections
6. Note the URL being used

Common patterns:
- `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- `wss://clob.polymarket.com/ws`
- `wss://ws.polymarket.com/book`

### Option 3: Check py-clob-client Source

The official Python client may have WebSocket examples:
- https://github.com/Polymarket/py-clob-client

## WebSocket Message Format

The exact message format depends on Polymarket's WebSocket API. Common patterns include:

### Subscription Message

When connecting, you typically send a subscription message:

```json
{
  "type": "subscribe",
  "channel": "book",
  "market": "<token-id>"
}
```

or

```json
{
  "auth": {},
  "markets": ["<token-id>"],
  "type": "market"
}
```

### Book Update Messages

The server sends book updates that typically look like:

```json
{
  "event_type": "book",
  "asset_id": "<token-id>",
  "timestamp": 1707440625000,
  "bids": [
    {"price": "0.999", "size": "100.0"},
    {"price": "0.998", "size": "50.0"}
  ],
  "asks": [
    {"price": "1.000", "size": "75.0"}
  ]
}
```

or

```json
{
  "type": "price_change",
  "market": "<token-id>",
  "bids": [[0.999, 100.0], [0.998, 50.0]],
  "asks": [[1.0, 75.0]]
}
```

## Updating the Script

If the WebSocket format differs from what's implemented, update `monitor_book_bids.py`:

### 1. Update the WebSocket URL

Change the `WS_URL` constant at the top of the file:

```python
WS_URL = "wss://your-actual-websocket-url.com/ws"
```

Or pass it via command line:

```bash
python monitor_book_bids.py --token-id <id> --ws-url wss://your-url.com/ws
```

### 2. Update the Subscription Message

Modify the `subscribe_msg` in the `subscribe_and_monitor` method:

```python
subscribe_msg = {
    # Your actual subscription format
    "type": "subscribe",
    "channel": "book",
    "market": self.token_id
}
```

### 3. Update Message Processing

Modify the `process_book_update` method to match the actual message structure:

```python
def process_book_update(self, data: dict):
    # Adjust based on actual message format
    bids = data.get("bids", [])  # or data["book"]["bids"], etc.
    
    for bid in bids:
        # Adjust based on bid format
        # Could be: {"price": "0.999", "size": "100"}
        # Or: [0.999, 100]
        # Or: {"p": 0.999, "s": 100}
        price = float(bid.get("price", bid[0]))
        size = float(bid.get("size", bid[1]))
        # ... rest of processing
```

## Testing Your Configuration

### 1. Enable Debug Output

Add print statements to see raw WebSocket messages:

```python
async for message in websocket:
    print(f"DEBUG: Received message: {message}")  # Add this
    try:
        data = json.loads(message)
        # ... rest of code
```

### 2. Test Connection

Run with a real token ID and watch for connection:

```bash
python monitor_book_bids.py --token-id <real-token-id>
```

Look for:
- "Subscribed to book updates" message
- Any error messages or connection issues
- Raw message output (if you added debug prints)

### 3. Verify Data

If connected but no bids are logged:
- Check that the market is actively trading
- Verify bids exist at 0.999 price level (check on Polymarket UI)
- Confirm the message format matches your processing code

## Alternative: REST API Polling

If WebSocket connection is difficult, you can alternatively poll the REST API:

```python
from py_clob_client.client import ClobClient
import time

client = ClobClient("https://clob.polymarket.com")
token_id = "<your-token-id>"

while True:
    book = client.get_order_book(token_id)
    for bid in book.bids:
        if abs(float(bid.price) - 0.999) < 0.0001:
            print(f"Bid at 0.999: size={bid.size}")
    time.sleep(1)  # Poll every second
```

This is less efficient but simpler to implement if WebSocket is problematic.

## Getting Help

If you're stuck configuring the WebSocket:
1. Check Polymarket's Discord or community forums
2. Review the py-clob-client repository for examples
3. Contact Polymarket developer support
4. Open an issue in this repository with error messages
