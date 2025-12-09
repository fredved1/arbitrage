"""
Configuration for Delta Neutral Arbitrage Bot
Copy this file to config.py and fill in your credentials.
"""

# ======== API CREDENTIALS ========
# Your Hyperliquid wallet private key
PRIVATE_KEY = "YOUR_PRIVATE_KEY_HERE"

# Main wallet address (the one with funds)
ACCOUNT_ADDRESS = "YOUR_WALLET_ADDRESS_HERE"

# ======== TRADING PAIRS ========
SPOT_SYMBOL = "@107"  # HYPE spot
PERP_SYMBOL = "HYPE"  # HYPE perpetual

# ======== STRATEGY THRESHOLDS ========
# Minimum spread to enter a position (0.15% = 0.0015)
MIN_SPREAD_THRESHOLD = 0.0015

# Exit when spread falls below this (0.03% = 0.0003)
EXIT_THRESHOLD = 0.0003

# Check funding rate before entry (skip if negative)
CHECK_FUNDING_RATE = True

# ======== RISK MANAGEMENT ========
# Maximum position size in USD
MAX_POSITION_USD = 12.0

# Enable dry-run mode (no real trades)
DRY_RUN = False

# ======== BOT SETTINGS ========
LOG_LEVEL = "INFO"

# Data collection
SAVE_SPREAD_LOG = True
SAVE_TRADE_LOG = True
SPREAD_LOG_FILE = "spread_log.json"
TRADE_LOG_FILE = "trade_log.json"

# ======== NETWORK ========
WS_URL = "wss://api.hyperliquid.xyz/ws"
API_URL = "https://api.hyperliquid.xyz"

# Reconnection settings
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY_SECONDS = 5
