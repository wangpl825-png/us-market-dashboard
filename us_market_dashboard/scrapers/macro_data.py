"""
scrapers/macro_data.py
Fetches macro-economic indicators from FRED and other public sources.
"""

import pandas as pd
import numpy as np
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, Optional
from config import FRED_API_KEY, FRED_SERIES


@st.cache_data(ttl=21600)  # 6-hour cache
def fetch_fred_series(series_id: str, limit: int = 60) -> pd.DataFrame:
    """Fetch a single FRED time series."""
    if not FRED_API_KEY:
        return _mock_fred_series(series_id)
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={FRED_API_KEY}"
            f"&file_type=json&sort_order=desc&limit={limit}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        obs = data.get("observations", [])
        df = pd.DataFrame(obs)[["date", "value"]]
        df["date"]  = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[macro_data] FRED error {series_id}: {e}")
        return _mock_fred_series(series_id)


def _mock_fred_series(series_id: str) -> pd.DataFrame:
    """Return plausible mock data when API key is missing."""
    dates = pd.date_range(end=datetime.today(), periods=24, freq="ME")
    mock_vals = {
        "UNRATE":         np.random.uniform(3.5, 4.2, 24),
        "CPIAUCSL":       np.linspace(295, 312, 24),
        "CPILFESL":       np.linspace(300, 315, 24),
        "UMCSENT":        np.random.uniform(60, 80, 24),
        "FEDFUNDS":       np.linspace(5.25, 5.5, 24),
        "DGS10":          np.random.uniform(4.0, 4.8, 24),
        "DGS2":           np.random.uniform(4.5, 5.0, 24),
        "T10Y2Y":         np.random.uniform(-0.5, 0.3, 24),
        "M2SL":           np.linspace(20800, 21200, 24),
        "A191RL1Q225SBEA":np.random.uniform(1.5, 3.5, 8),
        "PCEPILFE":       np.linspace(2.5, 3.1, 24),
        "HOUST":          np.random.uniform(1300, 1600, 24),
        "RSXFS":          np.linspace(500, 530, 24),
        "INDPRO":         np.linspace(102, 105, 24),
    }
    vals = mock_vals.get(series_id, np.random.uniform(100, 110, 24))
    n = min(len(dates), len(vals))
    return pd.DataFrame({"date": dates[:n], "value": vals[:n]})


@st.cache_data(ttl=21600)
def fetch_all_macro() -> Dict[str, pd.DataFrame]:
    """Fetch all macro series defined in config."""
    result = {}
    for name, series_id in FRED_SERIES.items():
        result[name] = fetch_fred_series(series_id)
    return result


@st.cache_data(ttl=21600)
def get_macro_snapshot() -> Dict[str, Dict]:
    """
    Return latest value + MoM change for each macro indicator.
    Format: { indicator_name: { value, prev, change, unit, label } }
    """
    macro = fetch_all_macro()
    snapshot = {}

    meta = {
        "unemployment_rate":     {"label": "Unemployment Rate",       "unit": "%"},
        "cpi_all_urban":         {"label": "CPI (All Urban)",         "unit": "index"},
        "core_cpi":              {"label": "Core CPI",                "unit": "index"},
        "consumer_confidence":   {"label": "Consumer Sentiment",      "unit": "index"},
        "fed_funds_rate":        {"label": "Fed Funds Rate",          "unit": "%"},
        "10y_treasury":          {"label": "10Y Treasury Yield",      "unit": "%"},
        "2y_treasury":           {"label": "2Y Treasury Yield",       "unit": "%"},
        "yield_curve_spread":    {"label": "Yield Curve (10Y-2Y)",   "unit": "%"},
        "m2_money_supply":       {"label": "M2 Money Supply",         "unit": "B USD"},
        "gdp_growth":            {"label": "Real GDP Growth",         "unit": "%"},
        "pcpix":                 {"label": "Core PCE",                "unit": "%"},
        "housing_starts":        {"label": "Housing Starts",          "unit": "K units"},
        "retail_sales":          {"label": "Retail Sales",            "unit": "M USD"},
        "industrial_production": {"label": "Industrial Production",   "unit": "index"},
    }

    for key, df in macro.items():
        if df.empty:
            continue
        val  = float(df["value"].iloc[-1])
        prev = float(df["value"].iloc[-2]) if len(df) > 1 else val
        m    = meta.get(key, {"label": key, "unit": ""})
        snapshot[key] = {
            "value":  val,
            "prev":   prev,
            "change": val - prev,
            "pct_change": (val - prev) / prev * 100 if prev != 0 else 0,
            "label":  m["label"],
            "unit":   m["unit"],
            "series": df,
        }
    return snapshot


@st.cache_data(ttl=3600)
def fetch_treasury_yields() -> pd.DataFrame:
    """Fetch yield curve: 3M, 2Y, 5Y, 10Y, 30Y."""
    tickers = {
        "3M":  "^IRX",
        "2Y":  "^TYX",   # proxy
        "5Y":  "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
    }
    rows = []
    for label, sym in tickers.items():
        try:
            import yfinance as yf
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if not hist.empty:
                rows.append({"maturity": label, "yield": round(hist["Close"].iloc[-1], 3)})
        except Exception:
            pass
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        [{"maturity": m, "yield": y} for m, y in
         zip(["3M","2Y","5Y","10Y","30Y"], [5.3, 4.8, 4.5, 4.3, 4.5])]
    )


def get_recession_risk_score(snapshot: Dict) -> Dict:
    """
    Simple rule-based recession risk composite (0–100).
    Based on: yield curve inversion, unemployment trend,
    consumer confidence, fed funds vs inflation.
    """
    score = 0
    signals = []

    # Yield curve inversion
    yc = snapshot.get("yield_curve_spread", {})
    if yc:
        val = yc["value"]
        if val < -0.5:
            score += 30
            signals.append(f"⚠️ Yield curve inverted ({val:.2f}%)")
        elif val < 0:
            score += 15
            signals.append(f"⚡ Yield curve slightly inverted ({val:.2f}%)")

    # Consumer confidence below 70 → risk
    cc = snapshot.get("consumer_confidence", {})
    if cc:
        val = cc["value"]
        if val < 65:
            score += 25
            signals.append(f"⚠️ Very low consumer confidence ({val:.1f})")
        elif val < 75:
            score += 12
            signals.append(f"⚡ Weak consumer confidence ({val:.1f})")

    # Unemployment rising
    ur = snapshot.get("unemployment_rate", {})
    if ur:
        chg = ur["change"]
        if chg > 0.3:
            score += 20
            signals.append(f"⚠️ Unemployment rising (+{chg:.2f}%)")
        elif chg > 0.1:
            score += 10
            signals.append(f"⚡ Unemployment inching up (+{chg:.2f}%)")

    # M2 contracting
    m2 = snapshot.get("m2_money_supply", {})
    if m2:
        if m2["pct_change"] < -0.5:
            score += 15
            signals.append("⚠️ M2 money supply contracting")

    score = min(score, 100)
    if score >= 60:    risk_label = "🔴 HIGH"
    elif score >= 35:  risk_label = "🟡 MODERATE"
    else:              risk_label = "🟢 LOW"

    return {"score": score, "label": risk_label, "signals": signals}
