"""
Orchestrates the full pipeline: batch-fetch historical data for the
whole universe (NSE and/or BSE) -> compute indicators + fundamentals
-> score -> rank -> return the day's top N buy/sell candidates for
both short-term and long-term horizons.

No broker login required — everything runs off free Yahoo Finance
data, so this can run fully unattended with zero manual steps.
"""
import pandas as pd

import data_fetcher
import indicators
import fundamentals
import screener


def run_full_screen(stocks: list[dict], progress_callback=None) -> pd.DataFrame:
    """
    stocks: list of {"symbol": ..., "exchange": "NSE"|"BSE"} (or plain
    symbol strings, treated as NSE, for backward compatibility).
    Returns a DataFrame, one row per symbol, with both short-term and
    long-term scores/signals, exchange tag, and key ratios.
    """
    if stocks and isinstance(stocks[0], str):
        stocks = [{"symbol": s, "exchange": "NSE"} for s in stocks]

    if progress_callback:
        progress_callback(0, len(stocks), "Fetching historical price data (batched)...")

    hist_by_symbol = data_fetcher.get_historical_bulk(stocks)
    exchange_by_symbol = {s["symbol"]: s["exchange"] for s in stocks}

    rows = []
    total = len(stocks)
    for i, s in enumerate(stocks):
        sym = s["symbol"]
        exch = s["exchange"]
        if progress_callback:
            progress_callback(i + 1, total, sym)

        hist = hist_by_symbol.get(sym)
        if hist is None or hist.empty:
            continue

        ind_df = indicators.enrich_with_indicators(hist)
        st = screener.score_short_term(ind_df)

        fund = fundamentals.get_fundamentals(sym, exchange=exch)
        lt = screener.score_long_term(fund, ind_df)

        rows.append({
            "symbol": sym,
            "exchange": exch,
            "name": fund.get("name", sym),
            "sector": fund.get("sector"),
            "last_close": st.get("last_close"),
            "pe_ratio": fund.get("pe_ratio"),
            "roe_pct": fund.get("roe_pct"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "revenue_growth_pct": fund.get("revenue_growth_pct"),
            "earnings_growth_pct": fund.get("earnings_growth_pct"),
            "market_cap_cr": fund.get("market_cap_cr"),
            "short_term_score": st.get("short_term_score"),
            "short_term_signal": st.get("short_term_signal"),
            "short_term_notes": "; ".join(st.get("notes", [])),
            "long_term_score": lt.get("long_term_score"),
            "long_term_signal": lt.get("long_term_signal"),
            "long_term_notes": "; ".join(lt.get("notes", [])),
        })

    return pd.DataFrame(rows)


def get_daily_top_calls(results_df: pd.DataFrame, top_n: int = None) -> dict:
    """
    Splits the full screen results into the day's top buy/sell calls
    for each horizon, across whichever exchange(s) were screened.
    """
    import config
    top_n = top_n or config.TOP_N
    df = results_df.copy()

    short_valid = df.dropna(subset=["short_term_score"])
    long_valid = df.dropna(subset=["long_term_score"])

    return {
        "short_term_buys": short_valid.sort_values("short_term_score", ascending=False).head(top_n),
        "short_term_sells": short_valid.sort_values("short_term_score", ascending=True).head(top_n),
        "long_term_buys": long_valid.sort_values("long_term_score", ascending=False).head(top_n),
        "long_term_sells": long_valid.sort_values("long_term_score", ascending=True).head(top_n),
    }
