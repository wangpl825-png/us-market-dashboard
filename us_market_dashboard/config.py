"""
config.py — Central configuration for US Market Dashboard
Reads API keys from Streamlit Secrets first, falls back to .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

def _get(key: str, default: str = "") -> str:
    """
    Read a secret: try Streamlit secrets first, then environment variable.
    This handles both Streamlit Cloud deployment and local .env usage.
    """
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key, default)

# ── API Keys ──────────────────────────────────────────────
FRED_API_KEY         = _get("FRED_API_KEY")
FINNHUB_API_KEY      = _get("FINNHUB_API_KEY")
NEWS_API_KEY         = _get("NEWS_API_KEY")
REDDIT_CLIENT_ID     = _get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = _get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT    = _get("REDDIT_USER_AGENT", "USMarketDashboard/1.0")
GEMINI_API_KEY       = _get("GEMINI_API_KEY")
POLYGON_API_KEY      = _get("POLYGON_API_KEY")

# ── Watchlist ─────────────────────────────────────────────
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "BAC", "GS", "BRK-B",
    "JNJ", "UNH",
    "XOM", "CVX",
    "WMT", "HD",
    "SPY", "QQQ", "DIA", "IWM", "GLD", "TLT", "VIX",
]

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "AMZN": "Consumer Discretionary",
    "META": "Technology", "TSLA": "Consumer Discretionary",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
    "BRK-B": "Financials", "JNJ": "Healthcare", "UNH": "Healthcare",
    "XOM": "Energy", "CVX": "Energy",
    "WMT": "Consumer Staples", "HD": "Consumer Discretionary",
    "SPY": "ETF", "QQQ": "ETF", "DIA": "ETF",
    "IWM": "ETF", "GLD": "ETF", "TLT": "ETF", "VIX": "Index",
}

# ── Historical Crash Periods ───────────────────────────────
CRASH_PERIODS = {
    "1973-1974 Oil Crisis":      ("1973-01-01", "1974-12-31"),
    "2000-2003 Dot-com Bubble":  ("2000-01-01", "2003-12-31"),
    "2007-2009 Financial Crisis": ("2007-01-01", "2009-12-31"),
    "2020 COVID-19 Crash":       ("2020-01-01", "2020-12-31"),
}

# ── Monte Carlo Settings ───────────────────────────────────
MC_SIMULATIONS   = 10_000
MC_TRADING_DAYS  = 21
MC_LOOKBACK_DAYS = 252

# ── FRED Series IDs ───────────────────────────────────────
FRED_SERIES = {
    "unemployment_rate":     "UNRATE",
    "cpi_all_urban":         "CPIAUCSL",
    "core_cpi":              "CPILFESL",
    "consumer_confidence":   "UMCSENT",
    "fed_funds_rate":        "FEDFUNDS",
    "10y_treasury":          "DGS10",
    "2y_treasury":           "DGS2",
    "yield_curve_spread":    "T10Y2Y",
    "m2_money_supply":       "M2SL",
    "gdp_growth":            "A191RL1Q225SBEA",
    "pcpix":                 "PCEPILFE",
    "housing_starts":        "HOUST",
    "retail_sales":          "RSXFS",
    "industrial_production": "INDPRO",
}

# ── News Sources RSS ──────────────────────────────────────
RSS_FEEDS = {
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Reuters Markets":  "https://feeds.reuters.com/reuters/companyNews",
    "BBC Business":     "http://feeds.bbci.co.uk/news/business/rss.xml",
    "MarketWatch":      "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "Seeking Alpha":    "https://seekingalpha.com/market_currents.xml",
    "Investing.com":    "https://www.investing.com/rss/news_25.rss",
    "Yahoo Finance":    "https://finance.yahoo.com/news/rssindex",
    "CNBC Markets":     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
}

# ── Reddit Subreddits ─────────────────────────────────────
REDDIT_SUBS = [
    "investing", "stocks", "wallstreetbets",
    "SecurityAnalysis", "StockMarket", "Economics",
]

# ── StockTwits ────────────────────────────────────────────
STOCKTWITS_TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"
STOCKTWITS_STREAM_URL   = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

# ── UI ────────────────────────────────────────────────────
PAGE_TITLE    = "🇺🇸 US Market Intelligence Dashboard"
PAGE_ICON     = "📈"
LAYOUT        = "wide"
SIDEBAR_STATE = "collapsed"

COLORS = {
    "positive":   "#00C853",
    "negative":   "#FF1744",
    "neutral":    "#90A4AE",
    "accent":     "#2979FF",
    "background": "#0E1117",
    "card":       "#1E2127",
    "text":       "#FAFAFA",
    "muted":      "#78909C",
}

PERCENTILE_COLORS = {
    "P99": "#00C853",
    "P90": "#69F0AE",
    "P50": "#FFD740",
    "P10": "#FF6D00",
    "P01": "#FF1744",
}
