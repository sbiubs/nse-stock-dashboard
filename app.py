"""
NSE Stock Dashboard — free data, no broker login required.
Run with:  streamlit run app.py
"""
import datetime as dt
import streamlit as st
import pandas as pd

import config
import data_fetcher
import indicators
import fundamentals
import screener
import recommender
import excel_export
import live_poller
import research_links

st.set_page_config(page_title="NSE Stock Dashboard", layout="wide", page_icon="📈")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("📈 NSE Stock Dashboard")
st.sidebar.caption("Prices & fundamentals via Yahoo Finance (free, delayed ~15-20 min) · No login required")

universe_choice = st.sidebar.radio("Universe", ["NIFTY 500", "NIFTY 50", "Custom watchlist"])
config.DEFAULT_UNIVERSE = {"NIFTY 500": "NIFTY500", "NIFTY 50": "NIFTY50", "Custom watchlist": "CUSTOM"}[universe_choice]

max_symbols = st.sidebar.slider(
    "Max symbols to screen (higher = slower)",
    min_value=20, max_value=500, value=100, step=10,
)

run_screen = st.sidebar.button("🔍 Run today's screen", type="primary")

st.sidebar.divider()
st.sidebar.caption(
    "⚠️ Scores are a transparent rule-based checklist (technical + fundamental), "
    "not a predictive model. Not investment advice — verify independently before "
    "acting, and size positions to your own risk tolerance."
)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("NSE Market Screener")
st.caption(f"As of {dt.datetime.now().strftime('%d %b %Y, %I:%M %p')}")

if "results_df" not in st.session_state:
    st.session_state.results_df = None
    st.session_state.top_calls = None

if run_screen:
    try:
        symbols = data_fetcher.get_universe_symbols()[:max_symbols]
    except Exception as e:
        st.error(f"Couldn't load universe list: {e}")
        st.stop()

    progress_bar = st.progress(0, text="Starting screen...")

    def _progress(i, total, sym):
        progress_bar.progress(min(i / total, 1.0), text=f"Screening {sym} ({i}/{total})")

    with st.spinner("Fetching data and scoring..."):
        results_df = recommender.run_full_screen(symbols, progress_callback=_progress)

    progress_bar.empty()
    st.session_state.results_df = results_df
    st.session_state.top_calls = recommender.get_daily_top_calls(results_df)
    st.success(f"Screened {len(results_df)} stocks.")

if st.session_state.results_df is None:
    st.info("👈 Click **Run today's screen** in the sidebar to fetch data and generate recommendations.")
    st.stop()

results_df = st.session_state.results_df
top_calls = st.session_state.top_calls

tab_overview, tab_live, tab_short, tab_long, tab_detail, tab_full = st.tabs(
    ["📊 Overview", "🔄 Live Snapshot", "⚡ Short-Term Calls", "🏛️ Long-Term Calls", "🔎 Search & Stock Detail", "📋 Full Screen"]
)

with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stocks screened", len(results_df))
    col2.metric("Short-term BUY signals", (results_df["short_term_signal"] == "BUY").sum())
    col3.metric("Short-term SELL signals", (results_df["short_term_signal"] == "SELL").sum())
    col4.metric("Long-term BUY signals", (results_df["long_term_signal"] == "BUY").sum())

    st.subheader("Today's Top 5 — Short-Term Buy")
    st.dataframe(top_calls["short_term_buys"][["symbol", "name", "last_close", "short_term_score", "short_term_notes"]], use_container_width=True, hide_index=True)

    st.subheader("Today's Top 5 — Long-Term Buy")
    st.dataframe(top_calls["long_term_buys"][["symbol", "name", "pe_ratio", "roe_pct", "long_term_score", "long_term_notes"]], use_container_width=True, hide_index=True)

    excel_bytes = excel_export.build_workbook(results_df, top_calls)
    st.download_button(
        "⬇️ Download full report as Excel",
        data=excel_bytes,
        file_name=f"nse_screen_{dt.date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with tab_live:
    st.subheader("🔄 Auto-Refreshing Price Snapshot")
    st.caption(
        "Polls Yahoo Finance on a timer — delayed ~15-20 minutes, not tick-by-tick "
        "real-time (that requires a paid broker feed). Fine for checking in once "
        "or twice a day; not meant for intraday trading decisions."
    )

    live_col1, live_col2 = st.columns([1, 1])
    poll_interval = live_col1.selectbox("Refresh every", [60, 300, 600, 900], index=1, format_func=lambda x: f"{x//60} min")
    alert_threshold_pct = live_col2.number_input("Alert on move ≥ (%)", min_value=0.5, max_value=10.0, value=3.0, step=0.5)

    if "live_alerts" not in st.session_state:
        st.session_state.live_alerts = []
    if "alerted_today" not in st.session_state:
        st.session_state.alerted_today = set()

    live_symbols = results_df["symbol"].tolist()

    @st.fragment(run_every=poll_interval)
    def render_live_snapshot():
        try:
            snap_df = live_poller.get_snapshot(live_symbols)
        except Exception as e:
            st.error(f"Couldn't fetch snapshot: {e}")
            return

        st.caption(f"Last refreshed: {dt.datetime.now().strftime('%H:%M:%S')} · {len(snap_df)} symbols")

        if snap_df.empty:
            st.info("No data returned — market may be closed or symbols unavailable.")
            return

        for row in snap_df.itertuples():
            if row.change_pct is not None and abs(row.change_pct) >= alert_threshold_pct:
                key = f"{row.symbol}_{int(row.change_pct // alert_threshold_pct)}"
                if key not in st.session_state.alerted_today:
                    st.session_state.alerted_today.add(key)
                    direction = "🟢 UP" if row.change_pct > 0 else "🔴 DOWN"
                    st.session_state.live_alerts.insert(0, {
                        "time": dt.datetime.now().strftime("%H:%M:%S"),
                        "symbol": row.symbol,
                        "message": f"{direction} {abs(row.change_pct):.1f}% move (LTP ₹{row.ltp})",
                    })
        st.session_state.live_alerts = st.session_state.live_alerts[:50]

        def _color_change(val):
            if pd.isna(val):
                return ""
            color = "#C6EFCE" if val > 0 else "#FFC7CE" if val < 0 else ""
            return f"background-color: {color}"

        styled = snap_df.style.map(_color_change, subset=["change_pct"])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=420)

    render_live_snapshot()

    st.subheader("🔔 Alerts Feed")
    st.caption(f"Fires when a stock moves ≥{alert_threshold_pct}% since last close. Notable moves worth a look, not trading signals by themselves.")

    @st.fragment(run_every=poll_interval)
    def render_alerts():
        if not st.session_state.live_alerts:
            st.info("No alerts yet — will populate as stocks make significant moves.")
        else:
            st.dataframe(pd.DataFrame(st.session_state.live_alerts), use_container_width=True, hide_index=True, height=250)

    render_alerts()

    st.divider()
    st.subheader("🔁 Auto-Rescore (refresh Buy/Sell advisory automatically)")
    auto_rescore = st.checkbox("Enable periodic auto-rescore")
    rescore_interval_min = st.selectbox("Rescore every", [15, 30, 60, 120], index=1, format_func=lambda x: f"{x} min", disabled=not auto_rescore)

    if auto_rescore:
        @st.fragment(run_every=rescore_interval_min * 60)
        def auto_rescore_fragment():
            try:
                symbols = data_fetcher.get_universe_symbols()[:max_symbols]
                results_df2 = recommender.run_full_screen(symbols)
                st.session_state.results_df = results_df2
                st.session_state.top_calls = recommender.get_daily_top_calls(results_df2)
                st.caption(f"✅ Advisory rescored at {dt.datetime.now().strftime('%H:%M:%S')} — check other tabs for updated calls.")
            except Exception as e:
                st.caption(f"⚠️ Rescore failed: {e}")

        auto_rescore_fragment()

with tab_short:
    st.subheader("Short-Term: Top 5 Buy")
    st.dataframe(top_calls["short_term_buys"], use_container_width=True, hide_index=True)
    st.subheader("Short-Term: Top 5 Sell")
    st.dataframe(top_calls["short_term_sells"], use_container_width=True, hide_index=True)

with tab_long:
    st.subheader("Long-Term: Top 5 Buy")
    st.dataframe(top_calls["long_term_buys"], use_container_width=True, hide_index=True)
    st.subheader("Long-Term: Top 5 Sell")
    st.dataframe(top_calls["long_term_sells"], use_container_width=True, hide_index=True)

with tab_detail:
    st.subheader("🔎 Look up any NSE stock")
    st.caption("Not limited to today's screened list — search any NSE-listed symbol directly.")

    search_col, pick_col = st.columns([1, 1])
    searched_symbol = search_col.text_input("Type an NSE symbol (e.g. WIPRO, ZOMATO, BAJFINANCE)").strip().upper()
    picked_symbol = pick_col.selectbox("...or pick from today's screen", ["—"] + sorted(results_df["symbol"].unique()))

    symbol = searched_symbol if searched_symbol else (picked_symbol if picked_symbol != "—" else None)

    if not symbol:
        st.info("👆 Type a symbol or pick one from today's screen to see details.")
    else:
        # If it's already in today's screen, reuse that row (no extra fetch needed);
        # otherwise fetch + score it fresh on the spot.
        existing = results_df[results_df["symbol"] == symbol]
        if not existing.empty:
            row = existing.iloc[0].to_dict()
        else:
            with st.spinner(f"Fetching {symbol}..."):
                hist_map = data_fetcher.get_historical_bulk([symbol])
                hist = hist_map.get(symbol)
                if hist is None or hist.empty:
                    st.error(f"Couldn't find data for '{symbol}' — check the symbol is a valid NSE trading symbol (not company name).")
                    st.stop()
                ind_df = indicators.enrich_with_indicators(hist)
                st_score = screener.score_short_term(ind_df)
                fund = fundamentals.get_fundamentals(symbol)
                lt_score = screener.score_long_term(fund, ind_df)
                row = {
                    "symbol": symbol, "name": fund.get("name", symbol),
                    "last_close": st_score.get("last_close"),
                    "pe_ratio": fund.get("pe_ratio"), "roe_pct": fund.get("roe_pct"),
                    "debt_to_equity": fund.get("debt_to_equity"), "market_cap_cr": fund.get("market_cap_cr"),
                    "short_term_score": st_score.get("short_term_score"), "short_term_signal": st_score.get("short_term_signal"),
                    "short_term_notes": "; ".join(st_score.get("notes", [])),
                    "long_term_score": lt_score.get("long_term_score"), "long_term_signal": lt_score.get("long_term_signal"),
                    "long_term_notes": "; ".join(lt_score.get("notes", [])),
                }

        c1, c2, c3 = st.columns(3)
        c1.metric("Last Close", f"₹{row['last_close']:.2f}" if pd.notna(row["last_close"]) else "N/A")
        c2.metric("Short-Term Score", row["short_term_score"], row["short_term_signal"])
        c3.metric("Long-Term Score", row["long_term_score"], row["long_term_signal"])

        st.write("**Fundamentals**")
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        fcol1.metric("P/E", f"{row['pe_ratio']:.1f}" if pd.notna(row["pe_ratio"]) else "N/A")
        fcol2.metric("ROE %", f"{row['roe_pct']:.1f}" if pd.notna(row["roe_pct"]) else "N/A")
        fcol3.metric("Debt/Equity", f"{row['debt_to_equity']:.2f}" if pd.notna(row["debt_to_equity"]) else "N/A")
        fcol4.metric("Mkt Cap (₹ Cr)", f"{row['market_cap_cr']:.0f}" if pd.notna(row["market_cap_cr"]) else "N/A")

        st.write("**Short-term reasoning:**", row["short_term_notes"] or "—")
        st.write("**Long-term reasoning:**", row["long_term_notes"] or "—")

        try:
            hist = data_fetcher.get_historical_bulk([symbol]).get(symbol)
            if hist is not None and not hist.empty:
                ind_df = indicators.enrich_with_indicators(hist)
                chart_df = ind_df.set_index("date")[["close", "sma_20", "sma_50", "sma_200"]]
                st.line_chart(chart_df)
            else:
                st.warning("No historical data available for chart.")
        except Exception as e:
            st.warning(f"Couldn't load chart: {e}")

        st.write("**📚 Research this stock elsewhere**")
        st.caption("Opens each platform's own page in a new tab — sign in there for any Pro/paid analyst content.")
        links = research_links.get_research_links(symbol)
        link_cols = st.columns(len(links))
        for col, (platform, url) in zip(link_cols, links.items()):
            col.link_button(platform, url, use_container_width=True)

with tab_full:
    st.dataframe(results_df, use_container_width=True, hide_index=True)
