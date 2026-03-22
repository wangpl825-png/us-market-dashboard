"""
components/charts.py
All Plotly chart builders for the dashboard.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from config import COLORS, PERCENTILE_COLORS


_TEMPLATE = "plotly_dark"
_BG       = "rgba(0,0,0,0)"
_FONT     = dict(family="Inter, sans-serif", color=COLORS["text"])


def _base_layout(**kwargs) -> dict:
    return dict(
        template=_TEMPLATE,
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=_FONT,
        margin=dict(l=10, r=10, t=40, b=10),
        **kwargs,
    )


# ── Candlestick + Indicators ──────────────────────────────

def candlestick_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Full OHLC candlestick with volume, MA lines, BB bands."""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.25, 0.20],
        vertical_spacing=0.03,
        subplot_titles=(f"{ticker} K線圖", "MACD", "RSI"),
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="OHLC",
        increasing_line_color=COLORS["positive"],
        decreasing_line_color=COLORS["negative"],
    ), row=1, col=1)

    # Bollinger Bands
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["bb_upper"], name="BB Upper",
            line=dict(color="rgba(100,100,255,0.5)", width=1, dash="dot"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["bb_lower"], name="BB Lower",
            line=dict(color="rgba(100,100,255,0.5)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(100,100,255,0.05)",
        ), row=1, col=1)

    # Moving Averages
    ma_colors = {"ma5": "#FFD740", "ma10": "#FF9800",
                 "ma50": "#00BCD4", "ma200": "#E91E63"}
    for ma, color in ma_colors.items():
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[ma], name=ma.upper(),
                line=dict(color=color, width=1),
            ), row=1, col=1)

    # Volume bars
    colors = [COLORS["positive"] if c >= o else COLORS["negative"]
              for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"], name="Volume",
        marker_color=colors, opacity=0.6,
    ), row=2, col=1)

    # MACD
    if "macd" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["macd"], name="MACD",
            line=dict(color=COLORS["accent"], width=1.5),
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["macd_signal"], name="Signal",
            line=dict(color=COLORS["negative"], width=1.5, dash="dash"),
        ), row=2, col=1)
        hist_colors = [COLORS["positive"] if v >= 0 else COLORS["negative"]
                       for v in df["macd_hist"]]
        fig.add_trace(go.Bar(
            x=df.index, y=df["macd_hist"], name="MACD Hist",
            marker_color=hist_colors, opacity=0.7,
        ), row=2, col=1)

    # RSI
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["rsi"], name="RSI",
            line=dict(color="#BA68C8", width=1.5),
        ), row=3, col=1)
        fig.add_hline(y=70, line=dict(color=COLORS["negative"], dash="dot", width=1), row=3, col=1)
        fig.add_hline(y=30, line=dict(color=COLORS["positive"], dash="dot", width=1), row=3, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,23,68,0.05)", row=3, col=1, line_width=0)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(0,200,83,0.05)", row=3, col=1, line_width=0)

    fig.update_layout(
        **_base_layout(height=620, title=f"{ticker} 技術分析",
                       showlegend=True, legend=dict(orientation="h", y=1.02)),
        xaxis_rangeslider_visible=False,
    )
    return fig


# ── Monte Carlo fan chart ──────────────────────────────────

def mc_fan_chart(
    mc_result: Dict,
    title: str = "Monte Carlo 模擬（一個月後）",
    n_display: int = 200,
) -> go.Figure:
    """Fan chart showing sample paths + percentile bands."""
    fig = go.Figure()
    price_paths = mc_result.get("price_paths")
    current     = mc_result.get("current_price", 1)
    n_days      = price_paths.shape[1] if price_paths is not None else 21
    days        = list(range(n_days + 1))

    if price_paths is not None:
        idx = np.random.choice(len(price_paths), min(n_display, len(price_paths)), replace=False)
        for i in idx:
            path = np.concatenate([[current], price_paths[i]])
            fig.add_trace(go.Scatter(
                x=days, y=path,
                mode="lines",
                line=dict(color="rgba(100,149,237,0.08)", width=0.5),
                showlegend=False, hoverinfo="skip",
            ))

    # Percentile lines
    final_returns = mc_result.get("final_returns", np.array([0]))
    pcts_vals = {
        "P99": np.percentile(final_returns, 99),
        "P90": np.percentile(final_returns, 90),
        "P50": np.percentile(final_returns, 50),
        "P10": np.percentile(final_returns, 10),
        "P01": np.percentile(final_returns, 1),
    }
    for label, ret in pcts_vals.items():
        end_price = current * (1 + ret / 100)
        fig.add_trace(go.Scatter(
            x=[0, n_days],
            y=[current, end_price],
            mode="lines+markers",
            name=f"{label} ({ret:+.1f}%)",
            line=dict(color=PERCENTILE_COLORS[label], width=2, dash="dash"),
            marker=dict(size=6),
        ))

    fig.add_hline(y=current, line=dict(color="white", dash="dot", width=1))
    fig.update_layout(**_base_layout(
        height=420, title=title,
        xaxis_title="交易日",
        yaxis_title="模擬價格 / 投資組合價值",
    ))
    return fig


def mc_distribution_chart(portfolio_returns: np.ndarray, title: str = "") -> go.Figure:
    """Histogram of simulated final returns with VaR annotations."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=portfolio_returns,
        nbinsx=100,
        marker_color=COLORS["accent"],
        opacity=0.75,
        name="模擬報酬分佈",
    ))
    # Colour losses red
    fig.add_vrect(
        x0=min(portfolio_returns), x1=0,
        fillcolor="rgba(255,23,68,0.1)", line_width=0,
        annotation_text="虧損區間", annotation_position="top left",
    )
    for p, color in [("P01", PERCENTILE_COLORS["P01"]),
                     ("P10", PERCENTILE_COLORS["P10"]),
                     ("P50", PERCENTILE_COLORS["P50"])]:
        val = np.percentile(portfolio_returns, int(p[1:]))
        fig.add_vline(x=val, line=dict(color=color, dash="dash", width=1.5),
                      annotation_text=f"{p}: {val:+.1f}%",
                      annotation_font_color=color)
    fig.update_layout(**_base_layout(
        height=350,
        title=title or "報酬率分佈（10,000次模擬）",
        xaxis_title="一個月報酬率 (%)",
        yaxis_title="模擬次數",
    ))
    return fig


# ── Macro / Yield Curve ────────────────────────────────────

def yield_curve_chart(df: pd.DataFrame) -> go.Figure:
    """Plot the US Treasury yield curve."""
    fig = go.Figure()
    if df.empty:
        return fig
    fig.add_trace(go.Scatter(
        x=df["maturity"], y=df["yield"],
        mode="lines+markers",
        line=dict(color=COLORS["accent"], width=2.5),
        marker=dict(size=8, color=COLORS["accent"]),
        fill="tozeroy", fillcolor="rgba(41,121,255,0.1)",
        name="殖利率曲線",
    ))
    fig.update_layout(**_base_layout(
        height=280, title="美債殖利率曲線",
        xaxis_title="到期期限", yaxis_title="殖利率 (%)",
    ))
    return fig


def macro_timeseries_chart(df: pd.DataFrame, label: str, unit: str) -> go.Figure:
    """Generic time-series chart for a macro indicator."""
    fig = go.Figure()
    if df.empty:
        return fig
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["value"],
        mode="lines",
        line=dict(color=COLORS["accent"], width=2),
        fill="tozeroy", fillcolor="rgba(41,121,255,0.08)",
        name=label,
    ))
    fig.update_layout(**_base_layout(
        height=220, title=f"{label} ({unit})",
        xaxis_title="", yaxis_title=unit,
        margin=dict(l=10, r=10, t=30, b=10),
    ))
    return fig


# ── Sentiment Gauge ────────────────────────────────────────

def sentiment_gauge(value: float, title: str = "市場情緒") -> go.Figure:
    """Gauge chart for Fear & Greed / custom sentiment score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis":       {"range": [0, 100], "tickfont": {"size": 10}},
            "bar":        {"color": COLORS["accent"]},
            "bgcolor":    COLORS["card"],
            "bordercolor": "gray",
            "steps": [
                {"range": [0, 25],   "color": COLORS["negative"]},
                {"range": [25, 45],  "color": "#FF6D00"},
                {"range": [45, 55],  "color": COLORS["neutral"]},
                {"range": [55, 75],  "color": "#69F0AE"},
                {"range": [75, 100], "color": COLORS["positive"]},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8, "value": value,
            },
        },
    ))
    fig.update_layout(**_base_layout(height=230, margin=dict(l=20, r=20, t=30, b=10)))
    return fig


# ── Portfolio donut chart ─────────────────────────────────

def portfolio_donut(holdings: Dict) -> go.Figure:
    """Donut chart showing portfolio weight distribution."""
    if not holdings:
        return go.Figure()
    labels  = list(holdings.keys())
    values  = [amt for _, amt in holdings.values()]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.5, textposition="auto",
        marker=dict(colors=px.colors.qualitative.Plotly),
    ))
    fig.update_layout(**_base_layout(
        height=300,
        title="投資組合配置",
        showlegend=True,
        legend=dict(orientation="h", y=-0.1),
    ))
    return fig


# ── Crash comparison bar chart ────────────────────────────

def crash_comparison_chart(crash_data: Dict) -> go.Figure:
    """Max drawdown comparison across crash periods."""
    labels, drawdowns = [], []
    for name, df in crash_data.items():
        if df.empty:
            continue
        cum_ret  = (1 + df["log_return"].apply(np.exp) - 1).cumprod()
        roll_max = cum_ret.cummax()
        drawdown = ((cum_ret - roll_max) / roll_max * 100).min()
        labels.append(name.split(" ")[0])   # short label
        drawdowns.append(round(float(drawdown), 1))

    fig = go.Figure(go.Bar(
        x=labels, y=drawdowns,
        marker_color=COLORS["negative"],
        text=[f"{d:.1f}%" for d in drawdowns],
        textposition="outside",
    ))
    fig.update_layout(**_base_layout(
        height=280,
        title="歷史崩盤最大跌幅比較 (%)",
        yaxis_title="最大跌幅 (%)",
    ))
    return fig


# ── Percentile comparison (before vs after hedge) ─────────

def percentile_comparison_chart(
    before: Dict,
    after: Dict,
) -> go.Figure:
    """Side-by-side grouped bar: before/after hedge percentiles."""
    labels  = ["P99", "P90", "P75", "P50", "P25", "P10", "P01"]
    before_pcts = [before.get("percentiles", {}).get(p, 0) for p in labels]
    after_pcts  = [after.get("percentiles",  {}).get(p, 0) for p in labels]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="原始配置", x=labels, y=before_pcts,
        marker_color=COLORS["accent"],
        text=[f"{v:+.1f}%" for v in before_pcts], textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="避險後配置", x=labels, y=after_pcts,
        marker_color=COLORS["positive"],
        text=[f"{v:+.1f}%" for v in after_pcts], textposition="outside",
    ))
    fig.add_hline(y=0, line=dict(color="white", dash="dot", width=1))
    fig.update_layout(**_base_layout(
        height=380,
        title="避險前後一個月報酬率百分位比較",
        barmode="group",
        yaxis_title="報酬率 (%)",
    ))
    return fig
