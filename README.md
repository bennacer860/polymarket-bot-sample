# Polymarket Bot

A Python bot for Polymarket with multiple modes:

1. **Single Trade Mode** – Place a test limit order given an event slug, price, and direction
2. **Trading Bot Mode** – For 15-min crypto Up/Down events: wait for event end, detect winning outcome, place 1 share @ 0.999 limit order on the winning side
3. **Book Monitor Mode** – Monitor WebSocket orderbook updates and log bids placed at the 0.999 price level
4. **Multi-Event Monitor Mode** – Monitor multiple event slugs simultaneously via WebSocket
5. **Continuous 15-Min Monitor Mode** – Automatically track current 15-minute crypto markets

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your PRIVATE_KEY and FUNDER address
```

## How to Run

Activate the virtual environment first (if not already active):

```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**Single trade** (place one test order):

```bash
python main.py trade --slug <event-slug> --price <0.0-1.0> --direction <up|down|yes|no>
```

**Trading bot** (15-min crypto – waits for event end, then places order on winning side):

```bash
python main.py bot --slug <event-slug>
# or
python run_bot.py <event-slug>
```

The event slug comes from the Polymarket URL: `https://polymarket.com/event/<slug>`.

## Usage

### Single Trade (Testing)

```bash
python main.py trade --slug <event-slug> --price <0.0-1.0> --direction <up|down|yes|no>
```

Example:
```bash
python main.py trade --slug btc-15m-20250101-1200 --price 0.50 --direction up
```

### Trading Bot (15-min Crypto)

```bash
python main.py bot --slug <event-slug>
```

Or use the dedicated entry point:
```bash
python run_bot.py <event-slug>
```

The bot will:
1. Fetch the event and validate it's a 15-min crypto market
2. Wait until the event end time + resolution buffer
3. Poll for resolution and determine the winning outcome
4. Place a limit order for 1 share @ $0.999 on the winning side

### Book Monitor (Analyze 0.999 Price Bids)

Monitor the Polymarket CLOB for bids placed at the 0.999 price level. This helps analyze when traders place their bids at this specific price point.

#### Option 1: WebSocket Monitor (Recommended)

Real-time monitoring using WebSocket connection:

First, get the token ID for your market:

```bash
python get_token_ids.py --slug <event-slug>
```

Then monitor the orderbook:

```bash
python monitor_book_bids.py --token-id <token-id>
```

#### Option 2: REST API Polling (Alternative)

If WebSocket connection is difficult, use the REST API polling version:

```bash
python monitor_book_bids_rest.py --token-id <token-id> --interval 1.0
```

This polls the orderbook every second (or your specified interval). It's simpler but less efficient than WebSocket.

#### Data Output

Both scripts will:
1. Monitor the specified token's orderbook (WebSocket) or poll it (REST)
2. Log every new bid placed at the 0.999 price level
3. Save data to `bids_0999.csv` with millisecond timestamps for analysis

The CSV output includes:
- `timestamp_ms`: Unix timestamp in milliseconds
- `timestamp_iso`: ISO 8601 formatted timestamp with milliseconds
- `price`: The bid price (should be 0.999)
- `size`: Total size of bids at this price level
- `size_change`: The increase in size from the previous update
- `token_id`: The token being monitored

You can then use this CSV file with any data visualization tool (Excel, pandas, matplotlib, etc.) to analyze the timing patterns of 0.999 bids.

To quickly visualize the data, use the included script:

```bash
# Quick text analysis (no dependencies)
python analyze_bids.py bids_0999.csv

# Visual charts (requires pandas & matplotlib)
pip install pandas matplotlib  # Install visualization dependencies
python visualize_bids.py bids_0999.csv
```

This will generate charts and statistics showing bid activity patterns over time. See `BOOK_MONITOR.md` for more details.

### Multi-Event Monitoring

Monitor multiple market events simultaneously with automatic market status tracking. See `MULTI_EVENT_MONITORING.md` for detailed documentation.

**Monitor specific event slugs:**

```bash
python monitor_multi_events.py multi --slugs slug1 slug2 slug3
```

**Continuously monitor 15-minute crypto markets:**

```bash
python monitor_multi_events.py continuous-15min --markets BTC ETH SOL
```

Features:
- Monitor multiple markets simultaneously via a single WebSocket connection
- Automatic market status tracking - closes WebSocket when all markets end
- Support for continuous 15-minute market monitoring
- Automatically generates correct slugs for current 15-minute periods
- All data saved to CSV for analysis

See `MULTI_EVENT_MONITORING.md` for complete usage examples and documentation.

## Configuration

See `.env.example` for required variables. You need a Polymarket account with funded USDC and the appropriate wallet setup (EOA, email/Magic, or browser proxy).

## Logging

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output. All trading actions and API responses are logged to help debug why orders didn't go through.
