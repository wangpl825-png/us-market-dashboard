"""
scrapers/market_data.py
Fetches OHLCV data + full technical indicator suite via yfinance & ta library.
"""

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
from ta import trend, momentum, volatility, volume as vol_ind
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import DEFAULT_TICKERS, CRASH_PERIODS, MC_LOOKBACK_DAYS


@st.cache_data(ttl=3600)
def fetch_ticker_info(ticker: str) -> Dict:
    """Fetch company metadata."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "name":        info.get("longName", ticker),
            "sector":      info.get("sector", "N/A"),
            "industry":    info.get("industry", "N/A"),
            "market_cap":  info.get("marketCap", 0),
            "pe_ratio":    info.get("trailingPE", None),
            "forward_pe":  info.get("forwardPE", None),
            "eps":         info.get("trailingEps", None),
            "dividend":    info.get("dividendYield", None),
            "52w_high":    info.get("fiftyTwoWeekHigh", None),
            "52w_low":     info.get("fiftyTwoWeekLow", None),
            "avg_volume":  info.get("averageVolume", None),
            "beta":        info.get("beta", None),
            "description": info.get("longBusinessSummary", ""),
        }
    except Exception:
        return {"name": ticker}


@st.cache_data(ttl=900)   # 15-min cache for price data
def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV and compute full technical indicators."""
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns=str.lower)
        df.dropna(inplace=True)

        # ── Moving Averages ──────────────────────────────
        for w in [5, 10, 20, 50, 200]:
            df[f"ma{w}"] = SMAIndicator(df["close"], window=w).sma_indicator()

        df["ema12"] = EMAIndicator(df["close"], window=12).ema_indicator()
        df["ema26"] = EMAIndicator(df["close"], window=26).ema_indicator()

        # ── MACD ─────────────────────────────────────────
        macd_obj = MACD(df["close"])
        df["macd"]        = macd_obj.macd()
        df["macd_signal"] = macd_obj.macd_signal()
        df["macd_hist"]   = macd_obj.macd_diff()

        # ── RSI ───────────────────────────────────────────
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()

        # ── Bollinger Bands ───────────────────────────────
        bb = BollingerBands(df["close"], window=20, window_dev=2)
        df["bb_upper"]  = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"]  = bb.bollinger_lband()
        df["bb_pct"]    = bb.bollinger_pband()   # %B

        # ── ATR ───────────────────────────────────────────
        df["atr"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        ).average_true_range()

        # ── Stochastic ────────────────────────────────────
        stoch = StochasticOscillator(df["high"], df["low"], df["close"])
        df["stoch_k"] = stoch.stoch()
        df["stoch_d"] = stoch.stoch_signal()

        # ── OBV ───────────────────────────────────────────
        df["obv"] = OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()

        # ── VWAP (daily rolling) ──────────────────────────
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

        # ── Daily returns & log returns ───────────────────
        df["daily_return"]     = df["close"].pct_change()
        df["log_return"]       = np.log(df["close"] / df["close"].shift(1))
        df["cumulative_return"] = (1 + df["daily_return"]).cumprod() - 1

        # ── Prev-day summary columns ──────────────────────
        df["prev_close"]  = df["close"].shift(1)
        df["price_change"] = df["close"] - df["prev_close"]
        df["pct_change"]   = df["daily_return"] * 100

        return df

    except Exception as e:
        print(f"[market_data] fetch_ohlcv error for {ticker}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=900)
def fetch_last_day_summary(tickers: List[str]) -> pd.DataFrame:
    """Return a one-row-per-ticker summary of the most recent trading day."""
    rows = []
    for ticker in tickers:
        df = fetch_ohlcv(ticker, period="5d")
        if df.empty:
            continue
        last = df.iloc[-1]
        rows.append({
            "ticker":       ticker,
            "close":        round(last["close"], 2),
            "change":       round(last.get("price_change", 0), 2),
            "pct_change":   round(last.get("pct_change", 0), 2),
            "volume":       int(last["volume"]),
            "rsi":          round(last.get("rsi", float("nan")), 1),
            "macd":         round(last.get("macd", float("nan")), 3),
            "macd_signal":  round(last.get("macd_signal", float("nan")), 3),
            "bb_pct":       round(last.get("bb_pct", float("nan")), 2),
            "atr":          round(last.get("atr", float("nan")), 2),
            "ma5":          round(last.get("ma5", float("nan")), 2),
            "ma10":         round(last.get("ma10", float("nan")), 2),
            "ma50":         round(last.get("ma50", float("nan")), 2),
            "ma200":        round(last.get("ma200", float("nan")), 2),
            "date":         df.index[-1].strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=86400)
def fetch_crash_data(ticker: str = "^GSPC") -> Dict[str, pd.DataFrame]:
    """Fetch SPX data for each historical crash window."""
    crash_dfs = {}
    for name, (start, end) in CRASH_PERIODS.items():
        try:
            df = yf.download(ticker, start=start, end=end,
                             auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=str.lower)
            df["log_return"] = np.log(df["close"] / df["close"].shift(1))
            df.dropna(inplace=True)
            crash_dfs[name] = df
        except Exception as e:
            print(f"[market_data] crash data error {name}: {e}")
    return crash_dfs


@st.cache_data(ttl=3600)
def fetch_vix() -> Tuple[float, float]:
    """Return (current VIX, previous close VIX)."""
    try:
        vix = yf.download("^VIX", period="5d", auto_adjust=True, progress=False)
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)
        closes = vix["Close"].dropna().values
        return float(closes[-1]), float(closes[-2]) if len(closes) > 1 else float(closes[-1])
    except Exception:
        return 20.0, 20.0


@st.cache_data(ttl=3600)
def fetch_dxy() -> Tuple[float, float]:
    """US Dollar Index (DXY)."""
    try:
        dxy = yf.download("DX-Y.NYB", period="5d", auto_adjust=True, progress=False)
        if isinstance(dxy.columns, pd.MultiIndex):
            dxy.columns = dxy.columns.get_level_values(0)
        closes = dxy["Close"].dropna().values
        return float(closes[-1]), float(closes[-2]) if len(closes) > 1 else float(closes[-1])
    except Exception:
        return 104.0, 104.0


@st.cache_data(ttl=3600)
def fetch_oil() -> Tuple[float, float]:
    """WTI Crude Oil price."""
    try:
        oil = yf.download("CL=F", period="5d", auto_adjust=True, progress=False)
        if isinstance(oil.columns, pd.MultiIndex):
            oil.columns = oil.columns.get_level_values(0)
        closes = oil["Close"].dropna().values
        return float(closes[-1]), float(closes[-2]) if len(closes) > 1 else float(closes[-1])
    except Exception:
        return 80.0, 80.0


@st.cache_data(ttl=3600)
def fetch_put_call_ratio() -> Optional[float]:
    """
    CBOE Put/Call ratio — fetched from CBOE public data.
    Falls back to None if unavailable.
    """
    try:
        url = "https://www.cboe.com/publish/scheduledtask/mktdata/datahouse/equitypc.csv"
        import requests
        r = requests.get(url, timeout=10)
        lines = r.text.strip().split("\n")
        # Last data line
        last = lines[-1].split(",")
        return float(last[2])   # Total P/C ratio column
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_fear_greed() -> Optional[Dict]:
    """CNN Fear & Greed index via alternative.me public API."""
    try:
        import requests
        r = requests.get(
            "https://fear-and-greed-index.p.rapidapi.com/v1/fgi",
            headers={
                "X-RapidAPI-Key": "no-key",
                "X-RapidAPI-Host": "fear-and-greed-index.p.rapidapi.com",
            },
            timeout=5,
        )
        # Fallback: alternative.me (crypto) as proxy sentiment
        r2 = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = r2.json()
        return {
            "value": int(data["data"][0]["value"]),
            "classification": data["data"][0]["value_classification"],
        }
    except Exception:
        return None


def get_signal(df: pd.DataFrame) -> str:
    """Simple composite signal: BUY / SELL / NEUTRAL."""
    if df.empty or len(df) < 5:
        return "NEUTRAL"
    last = df.iloc[-1]
    score = 0
    # RSI
    rsi = last.get("rsi", 50)
    if rsi < 30:   score += 2
    elif rsi < 45: score += 1
    elif rsi > 70: score -= 2
    elif rsi > 55: score -= 1
    # MACD
    if last.get("macd", 0) > last.get("macd_signal", 0): score += 1
    else: score -= 1
    # Price vs MA200
    if last["close"] > last.get("ma200", last["close"]): score += 1
    else: score -= 1
    # BB %B
    bb = last.get("bb_pct", 0.5)
    if bb < 0.2:   score += 1
    elif bb > 0.8: score -= 1

    if score >= 3:   return "BUY 🟢"
    elif score <= -3: return "SELL 🔴"
    else:             return "NEUTRAL 🟡"
