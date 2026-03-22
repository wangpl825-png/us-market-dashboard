"""
simulation/monte_carlo.py
Monte Carlo simulation engine.
Combines recent 252-day returns with historical crash period returns
to simulate a portfolio's 1-month forward distribution (10,000 paths).
"""

import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
from typing import Dict, List, Tuple, Optional
from config import MC_SIMULATIONS, MC_TRADING_DAYS, MC_LOOKBACK_DAYS, CRASH_PERIODS


# ── Data helpers ──────────────────────────────────────────

@st.cache_data(ttl=3600)
def _get_returns(ticker: str) -> np.ndarray:
    """
    Download log-returns for a ticker combining:
    (a) most recent 252 trading days
    (b) all four historical crash windows
    Returns a flat 1-D numpy array of daily log returns.
    """
    all_returns = []

    # Recent history
    try:
        df = yf.download(ticker, period="1y", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        closes = df["Close"].dropna()
        recent_lr = np.log(closes / closes.shift(1)).dropna().values
        all_returns.append(recent_lr[-MC_LOOKBACK_DAYS:])
    except Exception as e:
        print(f"[mc] recent returns error {ticker}: {e}")

    # Historical crash windows
    for name, (start, end) in CRASH_PERIODS.items():
        try:
            df = yf.download(ticker, start=start, end=end,
                             auto_adjust=True, progress=False)
            if df.empty:
                raise ValueError("empty")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            closes = df["Close"].dropna()
            lr = np.log(closes / closes.shift(1)).dropna().values
            all_returns.append(lr)
        except Exception:
            # Fallback: use SPY/^GSPC proxy
            try:
                proxy = "SPY"
                df = yf.download(proxy, start=start, end=end,
                                 auto_adjust=True, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                closes = df["Close"].dropna()
                lr = np.log(closes / closes.shift(1)).dropna().values
                all_returns.append(lr)
            except Exception:
                pass

    if not all_returns:
        # Last resort: Gaussian with SPY-like params
        return np.random.normal(0.0003, 0.012, MC_LOOKBACK_DAYS * 2)

    return np.concatenate(all_returns)


def _bootstrap_paths(
    returns: np.ndarray,
    n_sims: int,
    n_days: int,
    seed: int = 42,
) -> np.ndarray:
    """
    Parametric + bootstrap hybrid:
    - Fit empirical distribution from returns
    - Draw n_sims × n_days samples (with replacement)
    Returns shape (n_sims, n_days).
    """
    rng = np.random.default_rng(seed)
    # Block bootstrap (block size = 5 trading days) to preserve autocorrelation
    block_size = 5
    n_blocks   = (n_days + block_size - 1) // block_size
    max_start  = len(returns) - block_size
    if max_start < 1:
        # Fall back to i.i.d. sampling
        return rng.choice(returns, size=(n_sims, n_days), replace=True)

    # Draw block start indices
    starts = rng.integers(0, max_start, size=(n_sims, n_blocks))
    paths  = np.zeros((n_sims, n_days))
    for s in range(n_sims):
        r_seq = np.concatenate([returns[starts[s, b]: starts[s, b] + block_size]
                                for b in range(n_blocks)])
        paths[s] = r_seq[:n_days]
    return paths


# ── Core simulator ────────────────────────────────────────

@st.cache_data(ttl=3600)
def run_single_asset_mc(
    ticker: str,
    current_price: float,
    n_sims: int = MC_SIMULATIONS,
    n_days: int = MC_TRADING_DAYS,
) -> Dict:
    """
    Run MC for a single asset.
    Returns dict with price/return distributions and percentile statistics.
    """
    returns = _get_returns(ticker)
    paths   = _bootstrap_paths(returns, n_sims, n_days)

    # Cumulative price paths: S_T = S_0 * exp(sum of log returns)
    cum_log_ret = paths.cumsum(axis=1)               # (n_sims, n_days)
    price_paths = current_price * np.exp(cum_log_ret) # (n_sims, n_days)
    final_prices = price_paths[:, -1]
    final_returns = (final_prices / current_price - 1) * 100  # %

    pcts = {
        "P99": float(np.percentile(final_returns, 99)),
        "P90": float(np.percentile(final_returns, 90)),
        "P75": float(np.percentile(final_returns, 75)),
        "P50": float(np.percentile(final_returns, 50)),
        "P25": float(np.percentile(final_returns, 25)),
        "P10": float(np.percentile(final_returns, 10)),
        "P01": float(np.percentile(final_returns, 1)),
    }

    loss_pct = float(np.mean(final_returns < 0) * 100)
    # Which percentile does loss start?
    sorted_ret = np.sort(final_returns)
    loss_idx   = np.searchsorted(sorted_ret, 0)
    loss_starts_at = round((1 - loss_idx / n_sims) * 100, 1)

    return {
        "ticker":           ticker,
        "current_price":    current_price,
        "percentiles":      pcts,
        "loss_probability": round(loss_pct, 1),
        "loss_starts_at":   loss_starts_at,   # e.g. 42 → loss starts at P42
        "price_paths":      price_paths,       # for chart (subset)
        "final_returns":    final_returns,
        "mean_return":      float(np.mean(final_returns)),
        "std_return":       float(np.std(final_returns)),
        "var_95":           float(np.percentile(final_returns, 5)),   # 95% VaR
        "cvar_95":          float(np.mean(final_returns[final_returns <= np.percentile(final_returns, 5)])),
    }


def run_portfolio_mc(
    holdings: Dict[str, Tuple[float, float]],
    n_sims: int = MC_SIMULATIONS,
    n_days: int = MC_TRADING_DAYS,
) -> Dict:
    """
    Run portfolio-level MC simulation.

    holdings: { ticker: (weight, dollar_amount) }
    Returns portfolio-level statistics.
    """
    if not holdings:
        return {}

    total_value = sum(amt for _, amt in holdings.values())
    weights     = np.array([amt / total_value for _, amt in holdings.values()])
    tickers     = list(holdings.keys())

    # Collect individual return paths
    all_paths = []
    for ticker in tickers:
        ticker_info = holdings[ticker]
        current_price_placeholder = ticker_info[1]  # dollar amount as proxy

        returns = _get_returns(ticker)
        paths   = _bootstrap_paths(returns, n_sims, n_days)
        cum_log = paths.cumsum(axis=1)
        ret_paths = np.exp(cum_log) - 1   # simple return each path
        all_paths.append(ret_paths[:, -1])  # final-day return per sim

    # Weighted portfolio return
    # shape: (n_assets, n_sims) → portfolio return per sim
    asset_returns = np.array(all_paths)                  # (n_assets, n_sims)
    portfolio_returns = (weights[:, None] * asset_returns).sum(axis=0) * 100  # %

    pcts = {
        "P99": float(np.percentile(portfolio_returns, 99)),
        "P90": float(np.percentile(portfolio_returns, 90)),
        "P75": float(np.percentile(portfolio_returns, 75)),
        "P50": float(np.percentile(portfolio_returns, 50)),
        "P25": float(np.percentile(portfolio_returns, 25)),
        "P10": float(np.percentile(portfolio_returns, 10)),
        "P01": float(np.percentile(portfolio_returns, 1)),
    }

    loss_pct  = float(np.mean(portfolio_returns < 0) * 100)
    sorted_r  = np.sort(portfolio_returns)
    loss_idx  = np.searchsorted(sorted_r, 0)
    loss_starts_at = round((1 - loss_idx / n_sims) * 100, 1)

    dollar_pcts = {k: total_value * v / 100 for k, v in pcts.items()}

    return {
        "total_value":         total_value,
        "percentiles":         pcts,
        "dollar_percentiles":  dollar_pcts,
        "loss_probability":    round(loss_pct, 1),
        "loss_starts_at":      loss_starts_at,
        "portfolio_returns":   portfolio_returns,
        "mean_return":         float(np.mean(portfolio_returns)),
        "std_return":          float(np.std(portfolio_returns)),
        "var_95":              float(np.percentile(portfolio_returns, 5)),
        "cvar_95":             float(np.mean(portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)])),
        # For summarizer compatibility
        "portfolio_p99":       pcts["P99"],
        "portfolio_p90":       pcts["P90"],
        "portfolio_p50":       pcts["P50"],
        "portfolio_p10":       pcts["P10"],
        "portfolio_p01":       pcts["P01"],
        "portfolio_mean":      float(np.mean(portfolio_returns)),
    }


def format_percentile_table(mc_results: Dict, total_value: float) -> pd.DataFrame:
    """Return a display DataFrame for the percentile table."""
    pcts = mc_results.get("percentiles", {})
    rows = []
    for label in ["P99", "P90", "P75", "P50", "P25", "P10", "P01"]:
        ret = pcts.get(label, 0)
        dollar_gl = total_value * ret / 100
        rows.append({
            "百分位":    label,
            "報酬率 (%)": f"{ret:+.2f}%",
            "損益 ($)":  f"${dollar_gl:+,.0f}",
            "結果":      "獲利 ✅" if ret >= 0 else "虧損 ❌",
        })
    return pd.DataFrame(rows)
