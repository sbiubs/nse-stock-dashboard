"""
Auto-refreshing price snapshot — polls Yahoo Finance on a timer instead
of holding an open WebSocket connection (that requires a broker feed).
Data is delayed ~15-20 min, which matches "check once or twice a day"
usage — this is not tick-by-tick real-time, and shouldn't be treated
as such for intraday trading decisions.

Polling interval has a sane floor (30s) to avoid hammering Yahoo's
free endpoint, which can start throttling/blocking aggressive callers.
"""
MIN_POLL_SECONDS = 30

import pandas as pd
import data_fetcher


def get_snapshot(symbols: list[str]) -> pd.DataFrame:
    """Thin wrapper kept separate from data_fetcher for a clean import in app.py's live tab."""
    return data_fetcher.get_snapshot_quotes(symbols)
