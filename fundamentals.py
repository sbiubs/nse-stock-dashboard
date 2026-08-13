"""
Fundamental data (P/E, ROE, Debt/Equity, profit growth, etc.) is NOT
available from Kite Connect or any broker API — it comes from company
filings, not exchange price feeds. This module pulls it from Yahoo
Finance via `yfinance`, using the ".NS" suffix for NSE-listed symbols.

Caveat: Yahoo's NSE fundamentals coverage is decent for large/mid-caps
but patchy for small-caps, and values refresh daily (not intraday) —
which is fine, since P/E and ROE don't meaningfully change intraday.
For mission-critical work, cross-check against Screener.in or your
company's data terminal before acting.
"""
import time
import pandas as pd
import yfinance as yf


def _safe_get(d: dict, key: str, default=None):
    val = d.get(key, default)
    return val if val is not None else default


def get_fundamentals(nse_symbol: str, exchange: str = "NSE") -> dict:
    """
    nse_symbol: plain trading symbol, e.g. "RELIANCE", "TCS" (or a BSE
    scrip code/short name when exchange="BSE").
    Returns a dict of key ratios; missing values come back as None so
    the caller can decide how to treat gaps (rather than silently
    defaulting to 0, which would distort scoring).
    """
    suffix = ".NS" if exchange == "NSE" else ".BO"
    ticker = yf.Ticker(f"{nse_symbol}{suffix}")
    try:
        info = ticker.info
    except Exception:
        return {"symbol": nse_symbol, "error": "fetch_failed"}

    return {
        "symbol": nse_symbol,
        "name": _safe_get(info, "longName", nse_symbol),
        "sector": _safe_get(info, "sector"),
        "pe_ratio": _safe_get(info, "trailingPE"),
        "forward_pe": _safe_get(info, "forwardPE"),
        "pb_ratio": _safe_get(info, "priceToBook"),
        "roe_pct": (_safe_get(info, "returnOnEquity") or 0) * 100 if info.get("returnOnEquity") is not None else None,
        "roa_pct": (_safe_get(info, "returnOnAssets") or 0) * 100 if info.get("returnOnAssets") is not None else None,
        "debt_to_equity": _safe_get(info, "debtToEquity"),
        "profit_margin_pct": (_safe_get(info, "profitMargins") or 0) * 100 if info.get("profitMargins") is not None else None,
        "revenue_growth_pct": (_safe_get(info, "revenueGrowth") or 0) * 100 if info.get("revenueGrowth") is not None else None,
        "earnings_growth_pct": (_safe_get(info, "earningsGrowth") or 0) * 100 if info.get("earningsGrowth") is not None else None,
        "dividend_yield_pct": (_safe_get(info, "dividendYield") or 0) * 100 if info.get("dividendYield") is not None else None,
        "market_cap_cr": (_safe_get(info, "marketCap") or 0) / 1e7 if info.get("marketCap") is not None else None,  # INR crore
        "52w_high": _safe_get(info, "fiftyTwoWeekHigh"),
        "52w_low": _safe_get(info, "fiftyTwoWeekLow"),
        "book_value": _safe_get(info, "bookValue"),
        "current_ratio": _safe_get(info, "currentRatio"),
    }


def get_fundamentals_bulk(nse_symbols: list[str], delay_sec: float = 0.15) -> pd.DataFrame:
    """Fetches fundamentals for a list of symbols with a small delay to be a polite API citizen."""
    rows = []
    for sym in nse_symbols:
        rows.append(get_fundamentals(sym))
        time.sleep(delay_sec)
    return pd.DataFrame(rows)
