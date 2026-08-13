"""
Generates one-click links out to external research/advisory platforms
for a given NSE symbol — so you can quickly cross-check a stock's
analyst calls, ratings, and research without manually searching each
site. These are plain hyperlinks, opened in your own browser under
your own login where relevant (e.g. MoneyControl Pro) — nothing here
fetches or stores content from those sites; that's a deliberate choice,
see the note in README.md about why this app doesn't scrape paid
platforms directly.

Where a platform's page URLs follow a predictable pattern (Screener,
NSE, Google Finance), we link straight to the stock's page. Where they
don't (MoneyControl, Trendlyne, Tickertape, StockEdge all use internal
slugs that combine the company name and an ID we don't have), we use a
site-scoped search link instead — one click still gets you there.
"""


def get_research_links(symbol: str) -> dict:
    symbol = symbol.strip().upper()
    return {
        "Screener.in": f"https://www.screener.in/company/{symbol}/",
        "NSE Official": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
        "Google Finance": f"https://www.google.com/finance/quote/{symbol}:NSE",
        "MoneyControl": f"https://www.google.com/search?q={symbol}+site:moneycontrol.com",
        "Trendlyne": f"https://www.google.com/search?q={symbol}+site:trendlyne.com",
        "Tickertape": f"https://www.google.com/search?q={symbol}+site:tickertape.in",
        "StockEdge": f"https://www.google.com/search?q={symbol}+site:stockedge.com",
    }
