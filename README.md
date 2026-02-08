# Polymarket Bot

A Python bot for Polymarket with two modes:

1. **Single Trade Mode** – Place a test limit order given an event slug, price, and direction
2. **Trading Bot Mode** – For 15-min crypto Up/Down events: wait for event end, detect winning outcome, place 1 share @ 0.999 limit order on the winning side

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

## Configuration

See `.env.example` for required variables. You need a Polymarket account with funded USDC and the appropriate wallet setup (EOA, email/Magic, or browser proxy).

## Logging

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output. All trading actions and API responses are logged to help debug why orders didn't go through.
