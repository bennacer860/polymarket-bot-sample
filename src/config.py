"""Configuration from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# Wallet / CLOB
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
FUNDER = os.getenv("FUNDER", "")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "1"))
CHAIN_ID = 137

# API endpoints
CLOB_HOST = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
GAMMA_API = os.getenv("GAMMA_API", "https://gamma-api.polymarket.com").rstrip("/")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Bot settings
RESOLUTION_BUFFER_SECONDS = 60  # Wait after endDate before polling for resolution
POLL_INTERVAL_SECONDS = 5
POST_RESOLUTION_ORDER_PRICE = 0.999
POST_RESOLUTION_ORDER_SIZE = 1.0

# Monitor settings
MARKET_STATUS_CHECK_INTERVAL = 60  # How often to check if markets are still active (seconds)
MONITOR_TARGET_PRICE = 0.999  # Price level to monitor for bids
