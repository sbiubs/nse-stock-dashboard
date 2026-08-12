"""
Live/delayed price + historical data, entirely via free sources —
no broker account, no API key, no daily login required.

Data sources:
  - Historical OHLCV + latest price: Yahoo Finance (yfinance), NSE
    symbols via the ".NS" suffix. Free, no signup. Quotes are delayed
    ~15-20 minutes during market hours (standard for free data — true
    tick-by-tick real-time requires a paid broker/vendor feed).
  - Universe list (Nifty 500 constituents): NSE's own public CSV,
    published by the exchange for exactly this kind of use.

Batch requests (yf.download with a ticker list) are used wherever
possible instead of one-symbol-at-a-time loops — this is both faster
and gentler on Yahoo's servers than hammering it with individual calls.
"""
import pandas as pd
import numpy as np
import yfinance as yf

import config


def get_nifty500_symbols() -> list[str]:
    """
    NSE publishes the official Nifty 500 constituent list as a public
    CSV, refreshed periodically by NSE on index reconstitution.
    """
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    df = pd.read_csv(url)
    return df["Symbol"].tolist()


def load_custom_watchlist() -> list[str]:
    df = pd.read_csv(config.CUSTOM_WATCHLIST_FILE)
    col = df.columns[0]
    return df[col].tolist()


def get_universe_symbols() -> list[str]:
    if config.DEFAULT_UNIVERSE == "CUSTOM":
        return load_custom_watchlist()
    elif config.DEFAULT_UNIVERSE == "NIFTY50":
        return get_nifty500_symbols()[:50]
    else:
        return get_nifty500_symbols()


def _normalize_single_ticker_df(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance returns different column shapes for 1 vs many tickers; normalize to lowercase OHLCV + date."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out = out.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    out = out.reset_index().rename(columns={"Date": "date", "Datetime": "date"})
    keep = ["date", "open", "high", "low", "close", "volume"]
    return out[[c for c in keep if c in out.columns]].dropna(subset=["close"])


def get_historical_bulk(symbols: list[str], period: str = "15mo") -> dict[str, pd.DataFrame]:
    """
    Fetches daily OHLCV history for many symbols in one batched request.
    15 months gives enough warm-up for a 200-day SMA. Returns a dict
    keyed by plain NSE symbol (no .NS suffix), each value a DataFrame
    with columns: date, open, high, low, close, volume.
    """
    if not symbols:
        return {}
    tickers = [f"{s}.NS" for s in symbols]
    raw = yf.download(
        tickers=tickers, period=period, interval="1d",
        group_by="ticker", threads=True, progress=False, auto_adjust=True,
    )

    result = {}
    if len(tickers) == 1:
        # single-ticker download returns flat columns, not grouped
        result[symbols[0]] = _normalize_single_ticker_df(raw)
        return result

    for sym, yf_sym in zip(symbols, tickers):
        try:
            sub = raw[yf_sym]
        except (KeyError, TypeError):
            continue
        norm = _normalize_single_ticker_df(sub)
        if not norm.empty:
            result[sym] = norm
    return result


def get_snapshot_quotes(symbols: list[str]) -> pd.DataFrame:
    """
    Latest available price + day change for a list of symbols, using
    the most recent 2 daily bars (delayed data — fine for a once/twice-
    a-day check-in, not tick-by-tick). One symbol per row.
    """
    hist = get_historical_bulk(symbols, period="5d")
    rows = []
    for sym, df in hist.items():
        if df.empty or len(df) < 1:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last
        change_pct = ((last["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else None
        rows.append({
            "symbol": sym,
            "ltp": round(float(last["close"]), 2),
            "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
            "day_open": float(last["open"]),
            "day_high": float(last["high"]),
            "day_low": float(last["low"]),
            "prev_close": float(prev["close"]),
            "volume": int(last["volume"]) if pd.notna(last["volume"]) else None,
            "as_of": last["date"].strftime("%Y-%m-%d") if pd.notna(last["date"]) else None,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("change_pct", ascending=False, na_position="last")
    return out
