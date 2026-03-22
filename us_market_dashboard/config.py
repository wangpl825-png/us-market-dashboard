"""
config.py — Central configuration for US Market Dashboard
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────
FRED_API_KEY      = os.getenv("FRED_API_KEY", "")
FINNHUB_API_KEY   = os.getenv("FINNHUB_API_KEY", "")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY", "")
REDDIT_CLIENT_ID  = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "USMarketDashboard/1.0")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY", "")

# ── Watchlist (S&P 500 major components + key ETFs) ───────
DEFAULT_TICKERS = [
    # Mega-cap Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    # Financials
    "JPM", "BAC", "GS", "BRK-B",
    # Healthcare
    "JNJ", "UNH",
    # Energy
    "XOM", "CVX",
    # Consumer
    "WMT", "HD",
    # Key ETFs
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
    "1973-1974 Oil Crisis":     ("1973-01-01", "1974-12-31"),
    "2000-2003 Dot-com Bubble": ("2000-01-01", "2003-12-31"),
    "2007-2009 Financial Crisis":("2007-01-01", "2009-12-31"),
    "2020 COVID-19 Crash":      ("2020-01-01", "2020-12-31"),
}

# ── Monte Carlo Settings ───────────────────────────────────
MC_SIMULATIONS    = 10_000
MC_TRADING_DAYS   = 21        # ~1 month
MC_LOOKBACK_DAYS  = 252       # 1 trading year

# ── FRED Series IDs ───────────────────────────────────────
FRED_SERIES = {
    "unemployment_rate":        "UNRATE",
    "cpi_all_urban":            "CPIAUCSL",
    "core_cpi":                 "CPILFESL",
    "consumer_confidence":      "UMCSENT",  # U of Michigan
    "fed_funds_rate":           "FEDFUNDS",
    "10y_treasury":             "DGS10",
    "2y_treasury":              "DGS2",
    "yield_curve_spread":       "T10Y2Y",   # 10Y-2Y spread
    "m2_money_supply":          "M2SL",
    "gdp_growth":               "A191RL1Q225SBEA",
    "pcpix":                    "PCEPILFE",  # Core PCE
    "housing_starts":           "HOUST",
    "retail_sales":             "RSXFS",
    "industrial_production":    "INDPRO",
}

# ── News Sources RSS ──────────────────────────────────────
RSS_FEEDS = {
    "Reuters Business":  "https://feeds.reuters.com/reuters/businessNews",
    "Reuters Markets":   "https://feeds.reuters.com/reuters/companyNews",
    "BBC Business":      "http://feeds.bbci.co.uk/news/business/rss.xml",
    "MarketWatch":       "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "Seeking Alpha":     "https://seekingalpha.com/market_currents.xml",
    "Investing.com":     "https://www.investing.com/rss/news_25.rss",
    "Yahoo Finance":     "https://finance.yahoo.com/news/rssindex",
    "CNBC Markets":      "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
}

# ── Reddit Subreddits ──────────────────────────────────────
REDDIT_SUBS = [
    "investing", "stocks", "wallstreetbets",
    "SecurityAnalysis", "StockMarket", "Economics",
]

# ── StockTwits trending endpoint (no auth) ─────────────────
STOCKTWITS_TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"
STOCKTWITS_STREAM_URL   = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"

# ── UI Settings ────────────────────────────────────────────
PAGE_TITLE      = "🇺🇸 US Market Intelligence Dashboard"
PAGE_ICON       = "📈"
LAYOUT          = "wide"
SIDEBAR_STATE   = "collapsed"   # mobile-friendly default

# Colour palette (dark professional theme)
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
