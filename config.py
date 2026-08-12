"""
Central configuration for the NSE Stock Dashboard.
No API keys or broker login required — all data comes from free,
public sources (Yahoo Finance for prices/fundamentals, NSE's public
CSV for the Nifty 500 constituent list).
"""
import os

# --- Universe to screen ---
DEFAULT_UNIVERSE = "NIFTY500"  # options: "NIFTY50", "NIFTY500", "CUSTOM"
CUSTOM_WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "custom_watchlist.csv")

# --- Screening thresholds (tune these to your own risk appetite) ---
SHORT_TERM_RULES = {
    "rsi_oversold": 35,       # RSI below this = potential buy signal
    "rsi_overbought": 70,     # RSI above this = potential sell signal
    "volume_surge_x": 1.8,    # today's volume vs 20-day avg volume, multiple
    "min_price": 20,          # ignore penny stocks below this price (INR)
}

LONG_TERM_RULES = {
    "max_pe": 40,             # avoid richly-valued stocks
    "min_roe": 12,            # minimum return on equity, %
    "max_debt_to_equity": 1.5,
    "min_profit_growth": 5,   # YoY profit growth, %
}

# How many buy/sell calls to surface per horizon
TOP_N = 5
