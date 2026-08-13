"""
Live/delayed price + historical data, entirely via free sources —
no broker account, no API key, no daily login required.

Data sources:
  - Historical OHLCV + latest price: Yahoo Finance (yfinance).
    NSE symbols use the ".NS" suffix, BSE symbols use ".BO".
  - NSE universe list (Nifty 500 constituents): NSE's own public CSV.
  - BSE universe list: BSE's own public scrip-list API. This endpoint
    can occasionally change or rate-limit — if it fails, fall back to
    a custom_bse_watchlist.csv (same pattern as the NSE custom list).

Every stock is represented internally as a dict: {"symbol": ..., "exchange": "NSE"|"BSE"}
so the rest of the pipeline can build the right Yahoo ticker (.NS/.BO)
and display which exchange a result came from.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import requests

import config


def _to_yf_ticker(symbol: str, exchange: str) -> str:
    suffix = ".NS" if exchange == "NSE" else ".BO"
    return f"{symbol}{suffix}"


def get_nifty500_symbols() -> list[dict]:
    """NSE's official Nifty 500 constituent list, published by the exchange."""
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    df = pd.read_csv(url)
    return [{"symbol": s, "exchange": "NSE"} for s in df["Symbol"].tolist()]


def get_nse_all_symbols() -> list[dict]:
    """
    NSE's complete list of listed equities (~2000 symbols), not just
    the Nifty 500 subset — this is NSE's own official published list.
    Filtered to SERIES == 'EQ' (ordinary equity shares) to exclude
    other instrument series (e.g. BE/SM) mixed into the same file.
    """
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    if "SERIES" in df.columns:
        df = df[df["SERIES"].str.strip() == "EQ"]
    return [{"symbol": s.strip(), "exchange": "NSE"} for s in df["SYMBOL"].tolist()]


def get_bse_equity_symbols(limit: int = -1) -> list[dict]:
    """
    Fetches BSE's own public list of active equity scrips. BSE requires
    a browser-like User-Agent header or it rejects the request outright.

    limit: number of scrips to return, or -1 (default) to use
    config.BSE_DEFAULT_LIMIT, or 0/None to fetch ALL active BSE equity
    scrips (thousands — screening all of them will be slow).

    If this endpoint is unreachable or its shape has changed, falls
    back to custom_bse_watchlist.csv (create this file yourself with
    a 'symbol' column of BSE scrip codes or short names, one per line)
    rather than silently returning nothing.
    """
    if limit == -1:
        limit = config.BSE_DEFAULT_LIMIT
    url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    params = {"Group": "", "Scripcode": "", "industry": "", "segment": "Equity", "status": "Active"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bseindia.com/",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows_to_use = data if not limit or limit <= 0 else data[:limit]
        symbols = []
        for row in rows_to_use:
            # BSE's response uses a short trading symbol when one exists,
            # otherwise the numeric scrip code works as a Yahoo ticker too.
            sym = row.get("scrip_id") or row.get("SC_NAME") or str(row.get("SC_CODE") or row.get("Scrip_cd"))
            if sym:
                symbols.append({"symbol": str(sym).strip(), "exchange": "BSE"})
        if symbols:
            return symbols
        raise ValueError("BSE API returned no usable rows")
    except Exception:
        return _load_bse_fallback()


def _load_bse_fallback() -> list[dict]:
    import os
    if os.path.exists(config.CUSTOM_BSE_WATCHLIST_FILE):
        df = pd.read_csv(config.CUSTOM_BSE_WATCHLIST_FILE)
        col = df.columns[0]
        return [{"symbol": str(s).strip(), "exchange": "BSE"} for s in df[col].tolist()]
    return []


def load_custom_watchlist() -> list[dict]:
    df = pd.read_csv(config.CUSTOM_WATCHLIST_FILE)
    col = df.columns[0]
    return [{"symbol": s, "exchange": "NSE"} for s in df[col].tolist()]


def get_universe_symbols() -> list[dict]:
    """Returns list of {"symbol": ..., "exchange": "NSE"|"BSE"} per config.EXCHANGE / config.DEFAULT_UNIVERSE."""
    if config.DEFAULT_UNIVERSE == "CUSTOM":
        nse_list = load_custom_watchlist()
    elif config.DEFAULT_UNIVERSE == "NIFTY50":
        nse_list = get_nifty500_symbols()[:50]
    elif config.DEFAULT_UNIVERSE == "NSE_ALL":
        nse_list = get_nse_all_symbols()
    else:
        nse_list = get_nifty500_symbols()

    if config.EXCHANGE == "NSE":
        return nse_list
    elif config.EXCHANGE == "BSE":
        return get_bse_equity_symbols()
    else:  # BOTH — interleave so a later [:max_symbols] slice doesn't
        # starve one exchange just because the other list is longer.
        bse_list = get_bse_equity_symbols()
        interleaved = []
        for a, b in zip(nse_list, bse_list):
            interleaved.append(a)
            interleaved.append(b)
        longer = nse_list[len(bse_list):] if len(nse_list) > len(bse_list) else bse_list[len(nse_list):]
        return interleaved + longer


def _normalize_single_ticker_df(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance returns different column shapes for 1 vs many tickers; normalize to lowercase OHLCV + date."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # Defensive: if a MultiIndex slipped through (e.g. a single-ticker
    # frame that still carries a redundant top level), flatten it.
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(-1)
    out = out.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    out = out.reset_index().rename(columns={"Date": "date", "Datetime": "date"})
    keep = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in ["open", "high", "low", "close", "volume"] if c not in out.columns]
    if missing:
        # Column names didn't match what we expected at all (e.g. an
        # unrecognized yfinance response shape) — return empty rather
        # than crashing, so the caller can show a clean "no data" message.
        return pd.DataFrame()
    return out[[c for c in keep if c in out.columns]].dropna(subset=["close"])


def get_historical_bulk(stocks: list[dict], period: str = "15mo") -> dict[str, pd.DataFrame]:
    """
    Fetches daily OHLCV history for many symbols (NSE and/or BSE) in
    one batched request per exchange. 15 months gives enough warm-up
    for a 200-day SMA. Returns a dict keyed by plain symbol (no
    exchange suffix) -> DataFrame with columns: date, open, high, low,
    close, volume.

    Accepts either a list of dicts {"symbol":..., "exchange":...} or,
    for backward compatibility, a plain list of NSE symbol strings.
    """
    if not stocks:
        return {}
    if isinstance(stocks[0], str):
        stocks = [{"symbol": s, "exchange": "NSE"} for s in stocks]

    symbols = [s["symbol"] for s in stocks]
    tickers = [_to_yf_ticker(s["symbol"], s["exchange"]) for s in stocks]

    raw = yf.download(
        tickers=tickers, period=period, interval="1d",
        group_by="ticker", threads=True, progress=False, auto_adjust=True,
    )

    result = {}
    if isinstance(raw.columns, pd.MultiIndex):
        # Multi-ticker shape — also what yfinance sometimes returns even
        # for a single ticker when group_by="ticker" is set, so this
        # path is checked by actual column shape, not by len(tickers).
        for sym, yf_sym in zip(symbols, tickers):
            try:
                sub = raw[yf_sym]
            except (KeyError, TypeError):
                continue
            norm = _normalize_single_ticker_df(sub)
            if not norm.empty:
                result[sym] = norm
    else:
        # Flat columns — single ticker, single-level result.
        norm = _normalize_single_ticker_df(raw)
        if not norm.empty and symbols:
            result[symbols[0]] = norm
    return result


def get_snapshot_quotes(stocks: list[dict]) -> pd.DataFrame:
    """
    Latest available price + day change for a list of symbols (NSE
    and/or BSE), using the most recent 2 daily bars — delayed data,
    fine for a once/twice-a-day check-in, not tick-by-tick.
    """
    if stocks and isinstance(stocks[0], str):
        stocks = [{"symbol": s, "exchange": "NSE"} for s in stocks]

    exchange_by_symbol = {s["symbol"]: s["exchange"] for s in stocks}
    hist = get_historical_bulk(stocks, period="5d")
    rows = []
    for sym, df in hist.items():
        if df.empty or len(df) < 1:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last
        change_pct = ((last["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else None
        rows.append({
            "symbol": sym,
            "exchange": exchange_by_symbol.get(sym, "NSE"),
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
