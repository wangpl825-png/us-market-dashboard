"""
utils/helpers.py — Shared utility functions.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Union, Optional
from config import COLORS


def fmt_price(val: float) -> str:
    return f"${val:,.2f}"

def fmt_pct(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"

def fmt_large(val: float) -> str:
    """Format large numbers with B/M/K suffix."""
    if abs(val) >= 1e12: return f"${val/1e12:.2f}T"
    if abs(val) >= 1e9:  return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6:  return f"${val/1e6:.2f}M"
    if abs(val) >= 1e3:  return f"${val/1e3:.1f}K"
    return f"${val:.2f}"

def color_value(val: float, positive_good: bool = True) -> str:
    """Return CSS color string for a value."""
    if val > 0:
        return COLORS["positive"] if positive_good else COLORS["negative"]
    elif val < 0:
        return COLORS["negative"] if positive_good else COLORS["positive"]
    return COLORS["neutral"]

def delta_arrow(val: float) -> str:
    """Return ▲/▼/─ arrow string."""
    if val > 0: return "▲"
    if val < 0: return "▼"
    return "─"


def metric_card_html(label: str, value: str, delta: str = "",
                     delta_color: str = "") -> str:
    """Return an HTML snippet for a styled metric card."""
    delta_html = ""
    if delta:
        color = delta_color or ("green" if delta.startswith("+") else "red")
        delta_html = f'<div style="font-size:0.8rem;color:{color};">{delta}</div>'
    return f"""
    <div style="
        background:{COLORS['card']};
        border-radius:10px;
        padding:14px 18px;
        margin:4px 0;
        border-left:3px solid {COLORS['accent']};
    ">
        <div style="font-size:0.7rem;color:{COLORS['muted']};text-transform:uppercase;">{label}</div>
        <div style="font-size:1.3rem;font-weight:700;color:{COLORS['text']};">{value}</div>
        {delta_html}
    </div>
    """


def parse_portfolio_input(raw: str) -> dict:
    """
    Parse user portfolio text input.
    Expected format (one per line):  TICKER, WEIGHT%, AMOUNT
    Example:  AAPL, 30, 30000
    Returns: { ticker: (weight_decimal, dollar_amount) }
    """
    holdings = {}
    total_weight = 0
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip().replace("%", "").replace("$", "").replace(",", "")
                 for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            ticker = parts[0].upper()
            weight = float(parts[1]) / 100 if float(parts[1]) > 1 else float(parts[1])
            amount = float(parts[2]) if len(parts) > 2 else 0
            holdings[ticker] = (weight, amount)
            total_weight += weight
        except ValueError:
            continue
    # Normalise weights if they don't sum to 1
    if holdings and abs(total_weight - 1.0) > 0.01:
        tw = sum(w for w, _ in holdings.values())
        holdings = {t: (w / tw, a) for t, (w, a) in holdings.items()}
    return holdings


def validate_portfolio(holdings: dict) -> tuple[bool, str]:
    """Basic validation of parsed portfolio."""
    if not holdings:
        return False, "請輸入至少一個持股。"
    if len(holdings) > 30:
        return False, "持股數量上限為30支。"
    weights = [w for w, _ in holdings.values()]
    if abs(sum(weights) - 1.0) > 0.05:
        return False, f"權重總和 = {sum(weights)*100:.1f}%，請確認配置正確。"
    return True, ""


def rsi_signal_text(rsi: float) -> str:
    if rsi >= 70: return "超買 🔴"
    if rsi <= 30: return "超賣 🟢"
    if rsi >= 60: return "偏強 🟡"
    if rsi <= 40: return "偏弱 🟡"
    return "中性 ⚪"


def vix_level_text(vix: float) -> tuple[str, str]:
    """Return (label, color) for a VIX level."""
    if vix >= 40: return "極度恐慌 😱", COLORS["negative"]
    if vix >= 30: return "高度恐慌 😨", "#FF6D00"
    if vix >= 20: return "中度波動 😟", COLORS["neutral"]
    if vix >= 12: return "正常 😐", COLORS["positive"]
    return "低波動 😌", COLORS["positive"]


def yield_curve_signal(spread: float) -> tuple[str, str]:
    """10Y-2Y spread interpretation."""
    if spread < -0.5: return "深度倒掛 ⚠️ 衰退警訊", COLORS["negative"]
    if spread < 0:    return "輕微倒掛 ⚡", "#FF6D00"
    if spread < 0.5:  return "趨於平坦", COLORS["neutral"]
    return "正常斜率 ✅", COLORS["positive"]
