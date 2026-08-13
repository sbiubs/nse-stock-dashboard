# NSE Stock Dashboard & Screener

A live-ish NSE market dashboard: prices and fundamentals from **Yahoo
Finance (free, no signup)**, and a rule-based screener that surfaces
the day's top 5 short-term and top 5 long-term buy/sell candidates —
plus a one-click Excel export.

**No broker account, no API key, no daily login required.** This runs
entirely on free public data sources.

## ⚠️ Read this first

- **This is decision support, not investment advice.** The "scores"
  are a transparent, rule-based checklist (RSI, moving averages,
  MACD, volume, P/E, ROE, debt/equity, growth) — not a predictive
  model. No tool can promise "accurate" daily calls; treat every
  signal as one input, verify independently, and size positions to
  your own risk tolerance. Consider talking to a SEBI-registered
  investment adviser for anything consequential.
- **Data is delayed ~15-20 minutes**, not tick-by-tick real-time —
  standard for free data. True real-time requires a paid broker/vendor
  feed (e.g. Zerodha Kite Connect, ₹2000/month). Fine for checking in
  once or twice a day; not meant for intraday/scalping decisions.
- **Yahoo's NSE coverage is solid for large/mid-caps, patchier for
  small-caps.** Cross-check anything important against Screener.in or
  another source before acting.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the dashboard
```bash
streamlit run app.py
```
Opens at `http://localhost:8501`. No credentials to enter — the
sidebar goes straight to picking your universe and running a screen.

## Using it

1. Pick a universe in the sidebar: Nifty 50, Nifty 500, or your own
   `custom_watchlist.csv` (edit that file directly — one symbol per
   line, NSE trading symbols like `RELIANCE`, `TCS`).
2. Set how many symbols to screen.
3. Click **Run today's screen**.
4. Browse tabs: Overview (top 5 calls), Live Snapshot (auto-refreshing
   delayed prices + move alerts), Short-Term Calls, Long-Term Calls,
   **Search & Stock Detail** (look up *any* NSE stock by symbol, not
   just today's screened list — scores it fresh on the spot, plus
   one-click links to Screener, MoneyControl, Trendlyne, Tickertape,
   StockEdge, NSE, and Google Finance for deeper research), and Full
   Screen (every stock, sortable).
5. Download the **Excel report** — color-coded Buy/Sell/Hold sheets,
   ready to file or share.

## Live Snapshot tab

Auto-refreshes on a timer you choose (1/5/10/15 min) by polling Yahoo
Finance — not a held-open real-time connection, since that requires a
paid feed. An **Alerts** feed flags any stock moving beyond a
threshold you set (default ±3%) since last close — a running log, not
a buy/sell instruction by itself. You can also opt into periodic
auto-rescore of the full Buy/Sell advisory (15/30/60/120 min) so the
other tabs update themselves without you clicking anything.

## Tuning the rules

Open `config.py` — `SHORT_TERM_RULES` and `LONG_TERM_RULES` control
every threshold (RSI levels, max P/E, min ROE, max debt/equity, etc.).
Adjust these to match your own risk appetite; the scoring logic in
`screener.py` is deliberately simple and readable so you can see exactly
why each stock got its score, and extend it if you want more signals.

## Hosting as a website

See `DEPLOYMENT.md` for the full walkthrough — Streamlit Community
Cloud (free), no secrets to configure since there's no API key.

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard (main entry point) |
| `config.py` | Screening thresholds, universe settings |
| `data_fetcher.py` | Batched historical + snapshot price data via Yahoo Finance |
| `indicators.py` | RSI, SMA/EMA, MACD, volume surge, ATR calculations |
| `fundamentals.py` | P/E, ROE, D/E, growth via Yahoo Finance |
| `screener.py` | Scoring rules (short-term technical, long-term fundamental) |
| `recommender.py` | Orchestrates the full screen, ranks top 5 buy/sell |
| `live_poller.py` | Auto-refresh snapshot polling for the Live tab |
| `research_links.py` | One-click links out to external research platforms per stock |
| `excel_export.py` | Color-coded multi-sheet Excel report builder |
| `custom_watchlist.csv` | Your own symbol list, if not using Nifty 50/500 |

## A note on external research platforms

Sites like Screener.in, MoneyControl, Trendlyne, Tickertape, Groww, and
Tijori all explicitly prohibit automated scraping in their terms of
service, and actively block bot traffic. This build intentionally
avoids scraping them — Yahoo Finance's data is public, free, and meant
for exactly this kind of programmatic use.

Instead, the **Search & Stock Detail** tab gives you one-click links
out to each platform's own page for any stock you look up (via
`research_links.py`) — so you can quickly check analyst calls, ratings,
or Pro-tier research on MoneyControl/Trendlyne/etc. under your own
login, without the app ever touching your credentials or their
content. If you have a paid data vendor subscription with an actual
API (some paid Trendlyne/Tijori tiers offer one), you're welcome to
swap in your own fetcher module using the same interface as
`data_fetcher.py`.
