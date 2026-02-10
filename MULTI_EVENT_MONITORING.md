# Multi-Event Monitoring

This document describes the multi-event monitoring capabilities added to the Polymarket bot.

## Overview

The bot now supports:
1. **Multi-event monitoring**: Monitor multiple event slugs simultaneously
2. **Continuous 15-minute market monitoring**: Automatically track current 15-minute crypto markets
3. **Market status tracking**: Automatically detect when markets end and close WebSocket connections

## New Features

### 1. Multiple Event Slug Monitoring

Monitor multiple markets at the same time via WebSocket. The monitor will:
- Subscribe to all token IDs across multiple markets
- Track market status periodically
- Automatically close the WebSocket when all markets have ended
- Save all bid data to a single CSV file

**Usage:**
```bash
python monitor_multi_events.py multi --slugs slug1 slug2 slug3
```

**Example:**
```bash
python monitor_multi_events.py multi \
  --slugs btc-15m-1707523200 eth-15m-1707523200 \
  --output my_bids.csv
```

### 2. Continuous 15-Minute Market Monitoring

Automatically monitor the current 15-minute markets for selected cryptocurrencies. The monitor will:
- Automatically generate the correct market slug for the current 15-minute period
- Monitor the markets until they end
- Automatically transition to the next 15-minute period
- Continue indefinitely until stopped

**Usage:**
```bash
python monitor_multi_events.py continuous-15min --markets BTC ETH SOL
```

**Supported Markets:**
- `BTC` - Bitcoin 15-minute markets
- `ETH` - Ethereum 15-minute markets  
- `SOL` - Solana 15-minute markets
- `XRP` - Ripple 15-minute markets

**Example:**
```bash
# Monitor BTC and ETH 15-minute markets continuously
python monitor_multi_events.py continuous-15min --markets BTC ETH
```

### 3. Market Status Tracking

The monitors now track market status and automatically:
- Check if markets are still active every 60 seconds (configurable)
- Detect when markets have ended (via `ended` or `closed` flags)
- Close WebSocket connections when all monitored markets have ended
- Log market status changes

## Code Organization

The code has been reorganized into logical modules:

```
src/
├── monitors/              # WebSocket monitoring logic
│   ├── multi_event_monitor.py       # Multi-event monitor
│   └── continuous_15min_monitor.py  # Continuous 15-min monitor
├── markets/               # Market-specific utilities
│   └── fifteen_min.py               # 15-minute market utilities
└── utils/                 # General utilities
```

### Key Modules

#### `src/markets/fifteen_min.py`

Utilities for working with 15-minute crypto markets:
- `get_current_15m_utc()`: Get current 15-minute timestamp block
- `get_market_slug()`: Generate market slug for a given crypto and timestamp
- `MARKET_IDS`: Mapping of crypto symbols to market ID prefixes

#### `src/monitors/multi_event_monitor.py`

WebSocket monitor for multiple events:
- Fetches token IDs for each event slug
- Subscribes to all tokens via WebSocket
- Tracks market status and closes when all markets end
- Processes and logs orderbook updates at target price (0.999)

#### `src/monitors/continuous_15min_monitor.py`

Continuous monitor for 15-minute markets:
- Generates slugs for current 15-minute period
- Uses `MultiEventMonitor` to monitor current markets
- Automatically transitions to next period when markets end

## Configuration

New configuration options in `src/config.py`:

```python
# Monitor settings
MARKET_STATUS_CHECK_INTERVAL = 60  # How often to check if markets are still active (seconds)
MONITOR_TARGET_PRICE = 0.999       # Price level to monitor for bids
```

## Examples

### Example 1: Monitor specific event slugs
```bash
python monitor_multi_events.py multi \
  --slugs will-btc-close-higher-on-january-25-2025-0515-pm-est-than-on-january-25-2025-0500-pm-est \
  --output btc_monitor.csv
```

### Example 2: Continuously monitor BTC 15-minute markets
```bash
python monitor_multi_events.py continuous-15min \
  --markets BTC \
  --output btc_15min.csv
```

### Example 3: Monitor multiple crypto 15-minute markets
```bash
python monitor_multi_events.py continuous-15min \
  --markets BTC ETH SOL XRP \
  --output crypto_15min.csv
```

### Example 4: Custom WebSocket URL
```bash
python monitor_multi_events.py multi \
  --slugs slug1 slug2 \
  --ws-url wss://custom-ws-endpoint.com/ws
```

## CSV Output Format

The monitors output CSV files with the following columns:

| Column | Description |
|--------|-------------|
| `timestamp_ms` | Unix timestamp in milliseconds |
| `timestamp_iso` | ISO timestamp in EST timezone |
| `price` | Price level of the order |
| `size` | Size of the order |
| `size_change` | Change in size from previous update |
| `side` | Whether this is a BID or ASK order |
| `token_id` | Token ID (market identifier) |
| `event_slug` | Event slug for the market |

## Implementation Details

### 15-Minute Market Slug Generation

The slug format for 15-minute markets is: `{market_base}-{timestamp}`

Where:
- `market_base` is the crypto-specific prefix (e.g., "btc-15m")
- `timestamp` is the Unix timestamp rounded down to the nearest 15-minute interval

Example: `btc-15m-1707523200`

### Market Status Checking

The monitor checks market status by:
1. Fetching the event from Gamma API
2. Checking the first market's `ended` or `closed` flags
3. Marking the market as inactive if either flag is true
4. Closing the WebSocket when all monitored markets are inactive

### WebSocket Subscription

The monitor subscribes to multiple token IDs in a single WebSocket connection:

```python
{
    "type": "subscribe",
    "assets_ids": [token_id_1, token_id_2, ...],
    "custom_feature_enabled": False
}
```

## Troubleshooting

### WebSocket Connection Issues

If the WebSocket fails to connect:
- Check the `--ws-url` parameter
- Verify network connectivity
- Check logs for specific error messages

### Market Not Found

If a market slug is not found:
- Verify the slug format matches Polymarket's expected format
- Check that the event exists on Polymarket
- For 15-minute markets, ensure the timestamp is for a valid market period

### No Token IDs Found

If token IDs cannot be fetched:
- Verify the market exists and has been created
- Check the Gamma API endpoint is accessible
- Review logs for API errors
