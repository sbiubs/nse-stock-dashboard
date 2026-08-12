"""
Rule-based scoring engine.

IMPORTANT HONESTY NOTE: these scores are a transparent, rule-based
heuristic — a weighted checklist, not a predictive model, and not
investment advice. There is no scoring system, free or paid, that can
promise "accurate" daily calls; markets are influenced by information
this tool has no access to (order flow, news, insider activity, macro
shocks). Treat every score as one input into your own judgement, not
a substitute for it.

Short-term score (0-100): built from technical signals on daily bars —
RSI positioning, moving-average trend/crossovers, MACD momentum, and
volume confirmation.

Long-term score (0-100): built from fundamentals — valuation (P/E, P/B),
profitability (ROE, margins), balance-sheet health (D/E, current ratio),
and growth (revenue/earnings growth) — plus the same trend filter so we
don't recommend a fundamentally cheap stock that's in a structural
downtrend.
"""
import pandas as pd
import numpy as np

import config


def score_short_term(ind_df: pd.DataFrame) -> dict:
    """ind_df: output of indicators.enrich_with_indicators(), needs >= 50 rows."""
    if ind_df is None or len(ind_df) < 50 or ind_df["sma_50"].isna().iloc[-1]:
        return {"short_term_score": None, "short_term_signal": "insufficient_data", "notes": []}

    last = ind_df.iloc[-1]
    notes = []
    score = 50  # neutral baseline

    rules = config.SHORT_TERM_RULES

    if last["close"] < rules["min_price"]:
        return {"short_term_score": None, "short_term_signal": "excluded_low_price", "notes": ["Below min price filter"]}

    # RSI positioning
    if pd.notna(last["rsi_14"]):
        if last["rsi_14"] < rules["rsi_oversold"]:
            score += 15
            notes.append(f"RSI oversold ({last['rsi_14']:.1f}) — potential bounce")
        elif last["rsi_14"] > rules["rsi_overbought"]:
            score -= 15
            notes.append(f"RSI overbought ({last['rsi_14']:.1f}) — extended, risk of pullback")

    # Trend: price vs moving averages
    if pd.notna(last["sma_20"]) and pd.notna(last["sma_50"]):
        if last["close"] > last["sma_20"] > last["sma_50"]:
            score += 15
            notes.append("Price above 20 & 50 SMA — short-term uptrend")
        elif last["close"] < last["sma_20"] < last["sma_50"]:
            score -= 15
            notes.append("Price below 20 & 50 SMA — short-term downtrend")

    # MACD momentum
    if pd.notna(last["macd_hist"]) and len(ind_df) > 1:
        prev_hist = ind_df.iloc[-2]["macd_hist"]
        if pd.notna(prev_hist):
            if last["macd_hist"] > 0 and prev_hist <= 0:
                score += 10
                notes.append("MACD bullish crossover")
            elif last["macd_hist"] < 0 and prev_hist >= 0:
                score -= 10
                notes.append("MACD bearish crossover")

    # Volume confirmation
    if pd.notna(last["vol_surge"]) and last["vol_surge"] > rules["volume_surge_x"]:
        # Direction of the surge matters — confirm with today's price move
        day_change = (last["close"] - last["open"]) / last["open"] if last["open"] else 0
        if day_change > 0:
            score += 10
            notes.append(f"Volume surge ({last['vol_surge']:.1f}x avg) on up move")
        else:
            score -= 10
            notes.append(f"Volume surge ({last['vol_surge']:.1f}x avg) on down move")

    score = float(np.clip(score, 0, 100))
    signal = "BUY" if score >= 65 else "SELL" if score <= 35 else "HOLD"
    return {"short_term_score": round(score, 1), "short_term_signal": signal, "notes": notes,
            "last_close": float(last["close"]), "atr_14": float(last["atr_14"]) if pd.notna(last["atr_14"]) else None}


def score_long_term(fund: dict, ind_df: pd.DataFrame = None) -> dict:
    """fund: one row (dict) from fundamentals.get_fundamentals(). ind_df optional, for trend filter."""
    notes = []
    score = 50
    rules = config.LONG_TERM_RULES

    pe = fund.get("pe_ratio")
    roe = fund.get("roe_pct")
    de = fund.get("debt_to_equity")
    growth = fund.get("earnings_growth_pct")

    have_any_data = any(v is not None for v in [pe, roe, de, growth])
    if not have_any_data:
        return {"long_term_score": None, "long_term_signal": "insufficient_data", "notes": ["No fundamental data available"]}

    if pe is not None:
        if 0 < pe <= rules["max_pe"]:
            score += 10
            notes.append(f"P/E {pe:.1f} within reasonable range")
        elif pe > rules["max_pe"]:
            score -= 10
            notes.append(f"P/E {pe:.1f} looks expensive")

    if roe is not None:
        if roe >= rules["min_roe"]:
            score += 15
            notes.append(f"ROE {roe:.1f}% — healthy capital efficiency")
        else:
            score -= 10
            notes.append(f"ROE {roe:.1f}% below threshold")

    if de is not None:
        # yfinance debtToEquity is typically already in percent-like terms (e.g. 45 = 0.45x); normalize defensively
        de_ratio = de / 100 if de > 5 else de
        if de_ratio <= rules["max_debt_to_equity"]:
            score += 10
            notes.append(f"Debt/Equity {de_ratio:.2f}x — manageable leverage")
        else:
            score -= 15
            notes.append(f"Debt/Equity {de_ratio:.2f}x — high leverage risk")

    if growth is not None:
        if growth >= rules["min_profit_growth"]:
            score += 15
            notes.append(f"Earnings growth {growth:.1f}% YoY")
        else:
            score -= 10
            notes.append(f"Weak/negative earnings growth ({growth:.1f}%)")

    # Long-term trend filter: avoid stocks in a structural downtrend even if "cheap"
    if ind_df is not None and len(ind_df) >= 200 and pd.notna(ind_df.iloc[-1].get("sma_200")):
        last_close = ind_df.iloc[-1]["close"]
        sma200 = ind_df.iloc[-1]["sma_200"]
        if last_close > sma200:
            score += 5
            notes.append("Trading above 200-day SMA — long-term uptrend intact")
        else:
            score -= 10
            notes.append("Trading below 200-day SMA — structural downtrend, caution")

    score = float(np.clip(score, 0, 100))
    signal = "BUY" if score >= 65 else "SELL" if score <= 35 else "HOLD"
    return {"long_term_score": round(score, 1), "long_term_signal": signal, "notes": notes}
