"""
app.py — US Market Intelligence Dashboard
Main Streamlit application entry point.

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

# ── Page config (must be first Streamlit call) ────────────
st.set_page_config(
    page_title="🇺🇸 US Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Internal imports ──────────────────────────────────────
from config import DEFAULT_TICKERS, COLORS, CRASH_PERIODS
from scrapers.market_data import (
    fetch_last_day_summary, fetch_ohlcv, fetch_ticker_info,
    fetch_crash_data, fetch_vix, fetch_dxy, fetch_oil,
    fetch_fear_greed, fetch_put_call_ratio, get_signal,
)
from scrapers.macro_data import (
    get_macro_snapshot, fetch_treasury_yields, get_recession_risk_score,
)
from scrapers.news_scraper import (
    get_all_news, fetch_finnhub_ticker_news, fetch_stocktwits_trending,
    compute_news_sentiment,
)
from analysis.summarizer import (
    summarize_news, compare_with_crashes, generate_hedge_strategy,
    summarize_ticker, analyze_overview, analyze_stock, analyze_macro,
    analyze_news_sentiment, analyze_mc_results, analyze_portfolio,
)
from simulation.monte_carlo import (
    run_single_asset_mc, run_portfolio_mc, format_percentile_table,
)
from components.charts import (
    candlestick_chart, mc_fan_chart, mc_distribution_chart,
    yield_curve_chart, macro_timeseries_chart, sentiment_gauge,
    portfolio_donut, crash_comparison_chart, percentile_comparison_chart,
)
from utils.helpers import (
    fmt_price, fmt_pct, fmt_large, metric_card_html,
    parse_portfolio_input, validate_portfolio,
    rsi_signal_text, vix_level_text, yield_curve_signal, delta_arrow,
)

# ── Glossary helper ───────────────────────────────────────
def show_glossary(terms: dict, title: str = "📖 名詞說明"):
    with st.expander(title, expanded=False):
        cols = st.columns(2)
        items = list(terms.items())
        half = (len(items) + 1) // 2
        for i, (term, desc) in enumerate(items):
            with cols[0 if i < half else 1]:
                st.markdown(f"**{term}**  \n{desc}")




# ── AI analysis section helper ────────────────────────────
def _ai_section(section_key: str, label: str, fn, *args, **kwargs):
    st.divider()
    st.subheader("🤖 AI 綜合解讀")
    result_key = f"ai_{section_key}"
    col_btn, col_tip = st.columns([2, 3])
    with col_btn:
        if st.button(f"✨ 生成 {label} 綜合分析",
                     key=f"btn_{section_key}", type="primary"):
            with st.spinner("Gemini AI 分析中..."):
                st.session_state[result_key] = fn(*args, **kwargs)
    with col_tip:
        st.caption("點擊按鈕，AI 將整合本頁所有數據，以白話文解讀市場狀況")
    if result_key in st.session_state and st.session_state[result_key]:
        st.markdown(
            f'''<div style="
                background:#1a2332;border-left:4px solid #2979FF;
                border-radius:8px;padding:16px 20px;margin-top:12px;
                font-size:0.9rem;line-height:1.8;color:#FAFAFA;
            ">{st.session_state[result_key]}</div>''',
            unsafe_allow_html=True,
        )

# ── Global CSS ────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  .stApp { background-color: #0E1117; }
  .block-container { padding: 0.8rem 1rem 2rem; max-width: 100%; }

  /* Mobile-friendly typography */
  h1 { font-size: clamp(1.1rem, 4vw, 1.6rem) !important; }
  h2 { font-size: clamp(0.95rem, 3vw, 1.3rem) !important; }
  h3 { font-size: clamp(0.85rem, 2.5vw, 1.1rem) !important; }
  p, li, .stMarkdown { font-size: clamp(0.78rem, 2.2vw, 0.95rem); }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {
    gap: 2px; overflow-x: auto; flex-wrap: nowrap;
  }
  .stTabs [data-baseweb="tab"] {
    font-size: 0.78rem; padding: 6px 10px; white-space: nowrap;
  }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #1E2127;
    border-radius: 10px;
    padding: 10px 14px;
    border-left: 3px solid #2979FF;
  }

  /* Dataframe */
  .stDataFrame { font-size: 0.78rem; }

  /* Scrollable news feed */
  .news-feed { max-height: 420px; overflow-y: auto; }

  /* Badge */
  .badge {
    display: inline-block;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 600;
    margin: 1px;
  }
  .badge-buy    { background:#004D40; color:#00C853; }
  .badge-sell   { background:#4A0000; color:#FF1744; }
  .badge-neutral{ background:#1C2A30; color:#90A4AE; }

  /* Hide Streamlit branding */
  #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════
est = pytz.timezone("US/Eastern")
now = datetime.now(est)
market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
is_weekday   = now.weekday() < 5
market_status = "🟢 開盤中" if (is_weekday and market_open <= now <= market_close) else "🔴 休市"

st.markdown(f"""
<div style='display:flex;justify-content:space-between;align-items:center;
            border-bottom:1px solid #2a2d35;padding-bottom:8px;margin-bottom:8px;'>
  <div>
    <span style='font-size:1.35rem;font-weight:800;'>🇺🇸 US Market Intelligence</span>
    <span style='font-size:0.75rem;color:#78909C;margin-left:8px;'>Dashboard</span>
  </div>
  <div style='text-align:right;'>
    <div style='font-size:0.75rem;color:#78909C;'>{now.strftime('%Y-%m-%d %H:%M')} EST</div>
    <div style='font-size:0.78rem;'>{market_status}</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════
tabs = st.tabs([
    "📊 總覽",
    "📈 股票",
    "🌐 總體經濟",
    "📰 新聞情緒",
    "🎲 Monte Carlo",
    "💼 我的投資組合",
    "⚙️ 設定",
])

(
    tab_overview, tab_stocks, tab_macro,
    tab_news, tab_mc, tab_portfolio, tab_settings,
) = tabs


# ══════════════════════════════════════════════════════════
#  TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════
with tab_overview:
    # ── Top KPI row ──────────────────────────────────────

    show_glossary({
        "VIX 恐慌指數": "衡量市場預期波動性的指標，又稱「恐懼指數」。VIX > 30 代表市場高度恐慌，< 15 代表市場平靜。",
        "美元指數 (DXY)": "追蹤美元相對於六大主要貨幣的強弱。DXY 上漲通常對黃金、新興市場不利。",
        "殖利率曲線 (Yield Curve)": "短期與長期公債利率的關係。10Y-2Y 利差為負（倒掛）時，歷史上常是衰退前兆。",
        "恐懼貪婪指數": "CNN 編制的綜合情緒指標（0-100）。0-25 極度恐懼，75-100 極度貪婪。",
        "Put/Call Ratio": "期權市場中賣權與買權的比例。> 1.0 代表市場偏空，< 0.7 代表市場偏多。",
        "Fed Funds Rate": "聯準會設定的基準利率，影響全球資金成本與股市估值。",
        "WTI 原油": "西德州中質原油，美國原油定價基準。油價上漲通常推升通膨。",
        "衰退風險評分": "本系統綜合殖利率曲線、失業率、消費者信心等指標計算的衰退機率分數。",
    }, "📖 本頁名詞說明（點擊展開）")

    with st.spinner("載入市場指標..."):
        vix_now, vix_prev   = fetch_vix()
        dxy_now, dxy_prev   = fetch_dxy()
        oil_now, oil_prev   = fetch_oil()
        macro_snap          = get_macro_snapshot()
        fear_greed          = fetch_fear_greed()
        pc_ratio            = fetch_put_call_ratio()

    vix_label, vix_color = vix_level_text(vix_now)
    yc_spread = macro_snap.get("yield_curve_spread", {}).get("value", 0)
    yc_label, yc_color   = yield_curve_signal(yc_spread)
    recession_risk        = get_recession_risk_score(macro_snap)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("VIX 恐慌指數", f"{vix_now:.1f}",
                  f"{delta_arrow(vix_now-vix_prev)} {vix_now-vix_prev:+.1f}")
        st.caption(f"<span style='color:{vix_color}'>{vix_label}</span>",
                   unsafe_allow_html=True)
    with c2:
        st.metric("美元指數 (DXY)", f"{dxy_now:.2f}",
                  f"{delta_arrow(dxy_now-dxy_prev)} {dxy_now-dxy_prev:+.2f}")
    with c3:
        st.metric("WTI 原油 ($/桶)", f"{oil_now:.1f}",
                  f"{delta_arrow(oil_now-oil_prev)} {oil_now-oil_prev:+.1f}")
    with c4:
        ffe = macro_snap.get("fed_funds_rate", {}).get("value", 0)
        st.metric("聯邦基金利率", f"{ffe:.2f}%")
    with c5:
        st.metric("衰退風險評分", f"{recession_risk['score']}/100",
                  recession_risk["label"])

    st.divider()

    # ── Yield curve + Fear & Greed ────────────────────────
    col_yc, col_fg = st.columns([2, 1])
    with col_yc:
        yc_df = fetch_treasury_yields()
        st.plotly_chart(yield_curve_chart(yc_df), use_container_width=True)
        yc_val = macro_snap.get("yield_curve_spread", {}).get("value", 0)
        st.caption(
            f"<span style='color:{yc_color}'>10Y-2Y 利差：{yc_val:+.2f}% — {yc_label}</span>",
            unsafe_allow_html=True,
        )
    with col_fg:
        fg_val = fear_greed["value"] if fear_greed else 50
        fg_cls = fear_greed["classification"] if fear_greed else "N/A"
        st.plotly_chart(
            sentiment_gauge(fg_val, f"恐懼貪婪指數\n{fg_cls}"),
            use_container_width=True,
        )
        if pc_ratio:
            st.metric("Put/Call Ratio", f"{pc_ratio:.2f}",
                      "偏空" if pc_ratio > 1.0 else "偏多")

    st.divider()

    # ── Market snapshot table ─────────────────────────────
    st.subheader("📋 前一交易日收盤總覽")
    with st.spinner("載入股票資料..."):
        summary_df = fetch_last_day_summary(
            st.session_state.get("watchlist", DEFAULT_TICKERS[:16])
        )

    if not summary_df.empty:
        def _style_row(row):
            colors = []
            for col in row.index:
                if col == "pct_change":
                    c = COLORS["positive"] if row["pct_change"] >= 0 else COLORS["negative"]
                    colors.append(f"color: {c}; font-weight:600")
                elif col == "rsi":
                    rsi = row.get("rsi", 50)
                    if rsi >= 70 or rsi <= 30:
                        colors.append(f"color: #FFD740")
                    else:
                        colors.append("")
                else:
                    colors.append("")
            return colors

        display_df = summary_df[[
            "ticker", "close", "change", "pct_change",
            "volume", "rsi", "macd", "atr", "ma5", "ma200", "date",
        ]].copy()
        display_df.columns = [
            "代碼", "收盤價", "漲跌", "漲跌幅%",
            "成交量", "RSI", "MACD", "ATR", "MA5", "MA200", "日期",
        ]
        st.dataframe(
            display_df.style.apply(_style_row, axis=1),
            use_container_width=True,
            height=420,
        )

    # ── Recession risk signals ────────────────────────────
    if recession_risk["signals"]:
        st.subheader(f"🚨 衰退風險信號 — {recession_risk['label']}")
        for sig in recession_risk["signals"]:
            st.warning(sig)


    # ── AI 綜合解讀 ───────────────────────────────────────
    _ai_section(
        "overview", "總覽",
        analyze_overview,
        vix_now, vix_prev, dxy_now, oil_now,
        yc_spread,
        macro_snap.get("fed_funds_rate", {}).get("value", 0),
        macro_snap.get("unemployment_rate", {}).get("value", 0),
        macro_snap.get("cpi_all_urban", {}).get("value", 0),
        fear_greed, pc_ratio,
        recession_risk["score"], recession_risk["label"],
    )

# ══════════════════════════════════════════════════════════
#  TAB 2 — STOCKS
# ══════════════════════════════════════════════════════════
with tab_stocks:

    show_glossary({
        "RSI (相對強弱指數)": "衡量股票超買超賣的動能指標（0-100）。> 70 為超買（可能回調），< 30 為超賣（可能反彈）。",
        "MACD": "移動平均收斂背離指標。MACD 線高於信號線為多頭訊號，反之為空頭訊號。",
        "布林通道 %B": "價格在布林通道中的相對位置。0.8 以上為超買，0.2 以下為超賣。",
        "ATR (真實波動幅度)": "衡量股票平均每日波動範圍，數值越大代表波動越劇烈。",
        "MA5 / MA10 / MA200": "5日、10日、200日移動平均線。價格站上 MA200 通常視為長線多頭訊號。",
        "Beta (貝塔值)": "衡量個股相對大盤的波動程度。Beta > 1 代表波動比大盤大，< 1 代表較穩定。",
        "Forward P/E": "預測本益比，以未來12個月預估EPS計算。數值越低代表估值相對便宜。",
        "殖利率 (Dividend Yield)": "每年股息佔股價的百分比，越高代表現金回報越豐厚。",
        "VaR (風險值)": "在95%信心水準下，未來一個月最多可能損失的金額。",
        "CVaR (條件風險值)": "在最差的5%情境下，平均損失金額。比VaR更能反映尾端風險。",
    }, "📖 本頁名詞說明（點擊展開）")

    col_sel, col_period = st.columns([3, 1])
    with col_sel:
        ticker = st.selectbox(
            "選擇股票",
            options=st.session_state.get("watchlist", DEFAULT_TICKERS),
            key="stock_selector",
        )
    with col_period:
        period = st.selectbox("時間範圍", ["3mo", "6mo", "1y", "2y", "5y"], index=2)

    with st.spinner(f"載入 {ticker} 資料..."):
        df   = fetch_ohlcv(ticker, period=period)
        info = fetch_ticker_info(ticker)
        signal = get_signal(df)

    if df.empty:
        st.error(f"無法取得 {ticker} 資料。")
    else:
        # ── Company header ────────────────────────────────
        last = df.iloc[-1]
        name = info.get("name", ticker)
        pct  = last.get("pct_change", 0)
        pct_color = COLORS["positive"] if pct >= 0 else COLORS["negative"]

        st.markdown(
            f"### {name} `{ticker}`  "
            f"<span style='color:{pct_color};font-size:1.1rem'>"
            f"{fmt_price(last['close'])} {fmt_pct(pct)}</span>",
            unsafe_allow_html=True,
        )

        # Signal badge
        badge_cls = "badge-buy" if "BUY" in signal else ("badge-sell" if "SELL" in signal else "badge-neutral")
        st.markdown(f'<span class="badge {badge_cls}">{signal}</span>',
                    unsafe_allow_html=True)

        # ── Key metrics ───────────────────────────────────
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1: st.metric("RSI (14)", f"{last.get('rsi',0):.1f}",
                            rsi_signal_text(last.get("rsi", 50)))
        with m2: st.metric("MACD", f"{last.get('macd',0):.3f}")
        with m3: st.metric("BB%B", f"{last.get('bb_pct',0):.2f}")
        with m4: st.metric("ATR", f"{last.get('atr',0):.2f}")
        with m5: st.metric("Beta", f"{info.get('beta','N/A')}")
        with m6: st.metric("Forward P/E", f"{info.get('forward_pe','N/A')}")

        # ── Candlestick chart ─────────────────────────────
        st.plotly_chart(candlestick_chart(df, ticker), use_container_width=True)

        # ── Company info + ticker news ────────────────────
        col_info, col_news = st.columns([1, 2])
        with col_info:
            st.markdown("**公司資訊**")
            st.markdown(f"""
| 指標 | 數值 |
|------|------|
| 市值 | {fmt_large(info.get('market_cap',0))} |
| 52周高 | {fmt_price(info.get('52w_high',0))} |
| 52周低 | {fmt_price(info.get('52w_low',0))} |
| 本益比 | {info.get('pe_ratio','N/A')} |
| EPS | {info.get('eps','N/A')} |
| 殖利率 | {(info.get('dividend',0) or 0)*100:.2f}% |
| 產業 | {info.get('industry','N/A')} |
""")
        with col_news:
            st.markdown("**相關新聞**")
            ticker_news = fetch_finnhub_ticker_news(ticker)
            if ticker_news:
                for art in ticker_news[:6]:
                    pub = art["published"].strftime("%m/%d") if hasattr(art["published"], "strftime") else ""
                    st.markdown(
                        f"[{art['title'][:80]}]({art['link']})  \n"
                        f"<small style='color:#78909C'>{art['source']} · {pub}</small>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("無可用新聞（請設定 FINNHUB_API_KEY）")

        # ── MC quick preview ──────────────────────────────
        st.divider()
        st.subheader("🎲 快速蒙地卡羅預覽（一個月）")
        with st.spinner("運算中（10,000次模擬）..."):
            mc_single = run_single_asset_mc(ticker, float(last["close"]))

        col_mc1, col_mc2 = st.columns(2)
        with col_mc1:
            st.plotly_chart(
                mc_fan_chart(mc_single, title=f"{ticker} 一個月價格模擬"),
                use_container_width=True,
            )
        with col_mc2:
            pct_tbl = format_percentile_table(mc_single, float(last["close"]))
            st.dataframe(pct_tbl, use_container_width=True, hide_index=True)
            st.metric("虧損機率", f"{mc_single['loss_probability']:.1f}%")
            st.metric("95% VaR", f"{mc_single['var_95']:+.1f}%")
            st.metric("95% CVaR", f"{mc_single['cvar_95']:+.1f}%")


    if not df.empty:
        last2 = df.iloc[-1]
        ticker_news2 = fetch_finnhub_ticker_news(ticker)
        news_titles2  = [str(a.get("title","")) for a in ticker_news2[:6]]
        _ai_section(
            f"stock_{ticker}", f"{ticker}",
            analyze_stock,
            ticker, info.get("name", ticker),
            float(last2["close"]), float(last2.get("pct_change", 0)),
            float(last2.get("rsi", 50)), float(last2.get("macd", 0)),
            float(last2.get("macd_signal", 0)), float(last2.get("bb_pct", 0.5)),
            float(last2.get("atr", 0)), float(last2.get("ma50", 0)),
            float(last2.get("ma200", 0)),
            info.get("pe_ratio"), info.get("forward_pe"), info.get("beta"),
            signal, news_titles2,
        )

# ══════════════════════════════════════════════════════════
#  TAB 3 — MACRO
# ══════════════════════════════════════════════════════════
with tab_macro:
    st.subheader("🌐 總體經濟指標")

    show_glossary({
        "CPI (消費者物價指數)": "衡量一籃子消費品價格變動，是最常用的通膨指標。年增超過2%為Fed警戒線。",
        "Core CPI (核心CPI)": "剔除食品與能源的CPI，更能反映長期通膨趨勢。",
        "Core PCE": "Fed最偏好的通膨指標，比CPI更能反映消費者實際支出結構。",
        "失業率 (Unemployment Rate)": "勞動力中失業人口的比例。< 4% 通常視為充分就業，上升超過0.5%是衰退警訊。",
        "消費者信心指數": "密西根大學調查，衡量民眾對經濟的樂觀程度（基準=100）。低於70代表悲觀。",
        "M2 貨幣供給": "流通中現金加上活期與定期存款的總量。M2收縮通常預示流動性緊縮。",
        "殖利率曲線 10Y-2Y": "10年期公債利率減去2年期的利差。負值（倒掛）歷史上在衰退前約12-18個月出現。",
        "住宅開工數": "新開工建設的住宅數量，反映房市景氣與民間投資意願。",
        "工業生產指數": "衡量製造業、採礦業與公用事業的產出水準，反映實體經濟強弱。",
        "零售銷售": "零售商的商品銷售額，直接反映消費者支出與經濟活力。",
    }, "📖 本頁名詞說明（點擊展開）")

    with st.spinner("載入 FRED 資料..."):
        macro_snap = get_macro_snapshot()

    # ── KPI grid ─────────────────────────────────────────
    macro_display = [
        "unemployment_rate", "cpi_all_urban", "core_cpi",
        "consumer_confidence", "fed_funds_rate",
        "10y_treasury", "2y_treasury", "yield_curve_spread",
        "m2_money_supply", "gdp_growth", "pcpix",
        "housing_starts",
    ]
    cols = st.columns(4)
    for i, key in enumerate(macro_display):
        snap = macro_snap.get(key, {})
        if not snap:
            continue
        val  = snap["value"]
        chg  = snap["change"]
        unit = snap["unit"]
        with cols[i % 4]:
            st.metric(
                snap["label"],
                f"{val:.2f} {unit}",
                f"{delta_arrow(chg)} {chg:+.3f}",
            )

    st.divider()

    # ── Charts for key indicators ────────────────────────
    st.subheader("📈 指標走勢")
    chart_keys = [
        ("unemployment_rate", "失業率", "%"),
        ("cpi_all_urban",     "CPI 指數", "index"),
        ("yield_curve_spread","殖利率曲線利差", "%"),
        ("m2_money_supply",   "M2 貨幣供給", "B USD"),
    ]
    for i in range(0, len(chart_keys), 2):
        c1, c2 = st.columns(2)
        for col, (key, label, unit) in zip([c1, c2], chart_keys[i:i+2]):
            df_s = macro_snap.get(key, {}).get("series", pd.DataFrame())
            if not df_s.empty:
                with col:
                    st.plotly_chart(
                        macro_timeseries_chart(df_s, label, unit),
                        use_container_width=True,
                    )

    # ── Crash comparison ─────────────────────────────────
    st.divider()
    st.subheader("📉 歷史崩盤比較")
    with st.spinner("載入歷史崩盤資料..."):
        crash_data = fetch_crash_data()
    st.plotly_chart(crash_comparison_chart(crash_data), use_container_width=True)

    # ── AI crash analysis ─────────────────────────────────
    if st.button("🤖 AI 歷史崩盤比較分析", key="crash_analysis_btn"):
        with st.spinner("AI 分析中..."):
            news_df  = get_all_news(include_reddit=False)
            news_lst = news_df.to_dict("records") if not news_df.empty else []
            sentiment = compute_news_sentiment(news_lst)
            yc_val    = macro_snap.get("yield_curve_spread", {}).get("value", 0)
            analysis  = compare_with_crashes(macro_snap, vix_now, yc_val, sentiment)
        st.markdown(analysis)


    # ── AI 綜合解讀 ───────────────────────────────────────
    macro_snap3 = get_macro_snapshot()
    _ai_section(
        "macro", "總體經濟",
        analyze_macro,
        macro_snap3.get("unemployment_rate", {}).get("value", 4.0),
        macro_snap3.get("unemployment_rate", {}).get("change", 0),
        macro_snap3.get("cpi_all_urban", {}).get("value", 300),
        macro_snap3.get("cpi_all_urban", {}).get("change", 0),
        macro_snap3.get("fed_funds_rate", {}).get("value", 5.25),
        macro_snap3.get("10y_treasury", {}).get("value", 4.3),
        macro_snap3.get("2y_treasury", {}).get("value", 4.8),
        macro_snap3.get("yield_curve_spread", {}).get("value", -0.3),
        macro_snap3.get("m2_money_supply", {}).get("value", 21000),
        macro_snap3.get("m2_money_supply", {}).get("pct_change", 0),
        macro_snap3.get("consumer_confidence", {}).get("value", 70),
        macro_snap3.get("gdp_growth", {}).get("value", 2.5),
        get_recession_risk_score(macro_snap3)["score"],
    )

# ══════════════════════════════════════════════════════════
#  TAB 4 — NEWS & SENTIMENT
# ══════════════════════════════════════════════════════════
with tab_news:
    st.subheader("📰 市場新聞與情緒分析")

    show_glossary({
        "情緒分析 (Sentiment Analysis)": "自動分析新聞標題的正負面傾向。偏多=看漲，偏空=看跌，中性=無明顯方向。",
        "StockTwits": "類似 Twitter 的股票投資社群平台，熱門股票代表散戶關注度高。",
        "RSS Feed": "新聞網站提供的自動更新訂閱格式，本系統透過此方式抓取最新財經新聞。",
        "偏多 (Bullish)": "預期股價將上漲的市場情緒或觀點。",
        "偏空 (Bearish)": "預期股價將下跌的市場情緒或觀點。",
    }, "📖 本頁名詞說明（點擊展開）")


    with st.spinner("載入新聞..."):
        news_df = get_all_news(include_reddit=True)

    if news_df.empty:
        st.warning("無法載入新聞。請確認 API Keys 設定。")
    else:
        news_list = news_df.to_dict("records")
        sentiment = compute_news_sentiment(news_list)

        # ── Sentiment summary ─────────────────────────────
        s1, s2, s3, s4 = st.columns(4)
        with s1: st.metric("總文章數", sentiment["total"])
        with s2: st.metric("偏多 🟢", f"{sentiment['bullish_pct']}%")
        with s3: st.metric("偏空 🔴", f"{sentiment['bearish_pct']}%")
        with s4: st.metric("中性 ⚪", f"{sentiment['neutral_pct']}%")

        # ── StockTwits trending ────────────────────────────
        trending = fetch_stocktwits_trending()
        if trending:
            st.caption("🔥 StockTwits 熱門：" + "  |  ".join(
                f"**{t['ticker']}**" for t in trending[:10]
            ))

        st.divider()

        # ── AI Summary ────────────────────────────────────
        col_sum, col_feed = st.columns([1, 1])
        with col_sum:
            st.markdown("**🤖 AI 新聞摘要**")
            if st.button("生成 AI 摘要", key="news_summary_btn"):
                with st.spinner("AI 分析中..."):
                    summary = summarize_news(news_list[:20])
                st.markdown(summary)
            else:
                st.caption("點擊按鈕生成 AI 摘要（需要 GEMINI_API_KEY）")

        with col_feed:
            st.markdown("**📡 最新新聞流**")
            # Source filter
            sources = ["全部"] + sorted(news_df["source"].unique().tolist())
            sel_src = st.selectbox("篩選來源", sources, key="news_source_filter")

            filtered = news_df if sel_src == "全部" else news_df[news_df["source"] == sel_src]

            st.markdown('<div class="news-feed">', unsafe_allow_html=True)
            for _, row in filtered.head(30).iterrows():
                pub_str = ""
                try:
                    pub_str = pd.to_datetime(row["published"]).strftime("%m/%d %H:%M")
                except Exception:
                    pass
                link    = str(row.get("link") or "#")
                title   = str(row.get("title") or "")
                source  = str(row.get("source") or "")
                st.markdown(
                    f"[{title[:90]}]({link})  \n"
                    f"<small style='color:#78909C'>{source} · {pub_str}</small>",
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)


    # ── AI 綜合解讀 ───────────────────────────────────────
    if not news_df.empty:
        top_headlines4 = [str(r.get("title","")) for _, r in news_df.head(8).iterrows()]
        trending4      = fetch_stocktwits_trending()
        vix4, _        = fetch_vix()
        _ai_section(
            "news", "新聞情緒",
            analyze_news_sentiment,
            sentiment["bullish_pct"], sentiment["bearish_pct"],
            sentiment["neutral_pct"], sentiment["total"],
            top_headlines4, trending4, vix4,
        )

# ══════════════════════════════════════════════════════════
#  TAB 5 — MONTE CARLO (Market-level)
# ══════════════════════════════════════════════════════════
with tab_mc:
    st.subheader("🎲 S&P 500 市場蒙地卡羅模擬")

    show_glossary({
        "蒙地卡羅模擬 (Monte Carlo)": "透過大量隨機模擬（本系統10,000次）來預測未來可能的結果範圍，而非單一預測值。",
        "百分位 (Percentile)": "P99代表10,000次模擬中排名第9,900好的結果，P1代表最差1%的情境。",
        "P50 (中位數)": "有一半的模擬結果比這個數字好，另一半比這個數字差，最接近「最可能的結果」。",
        "VaR (Value at Risk)": "在95%信心水準下，一個月內最壞可能損失多少。例如VaR=-8%代表有5%機率損失超過8%。",
        "CVaR (條件風險值)": "最差5%情境的平均損失，比VaR更保守，用於評估極端風險。",
        "Block Bootstrap": "本系統使用的抽樣方法，以5天為一組抽取歷史報酬，保留市場連續崩跌的特性。",
        "對數報酬 (Log Return)": "計算股票漲跌時使用的數學方式，比百分比報酬更適合長期累積計算。",
        "GBM (幾何布朗運動)": "假設股價走勢具隨機性的數學模型，是蒙地卡羅模擬的理論基礎。",
    }, "📖 本頁名詞說明（點擊展開）")

    st.caption("使用過去252交易日 + 四大歷史崩盤數據，運算10,000次")

    mc_ticker = st.selectbox(
        "選擇指數/ETF",
        ["SPY", "QQQ", "DIA", "IWM", "^GSPC", "^NDX"],
        key="mc_index_selector",
    )

    if st.button("▶ 執行模擬", key="run_mc_btn"):
        with st.spinner(f"執行 {mc_ticker} 蒙地卡羅模擬（10,000次）..."):
            spy_df   = fetch_ohlcv(mc_ticker, period="5d")
            cur_price = float(spy_df["close"].iloc[-1]) if not spy_df.empty else 500.0
            mc_res   = run_single_asset_mc(mc_ticker, cur_price)
            st.session_state["market_mc"] = mc_res

    mc_res = st.session_state.get("market_mc")
    if mc_res:
        col_fan, col_hist = st.columns(2)
        with col_fan:
            st.plotly_chart(
                mc_fan_chart(mc_res, title=f"{mc_ticker} 一個月模擬路徑"),
                use_container_width=True,
            )
        with col_hist:
            st.plotly_chart(
                mc_distribution_chart(mc_res["final_returns"],
                                      title=f"{mc_ticker} 報酬率分佈"),
                use_container_width=True,
            )

        st.subheader("📊 百分位統計")
        pct_df = format_percentile_table(mc_res, mc_res["current_price"])
        st.dataframe(pct_df, use_container_width=True, hide_index=True)

        ri1, ri2, ri3, ri4 = st.columns(4)
        with ri1: st.metric("預期報酬 (P50)", f"{mc_res['percentiles']['P50']:+.2f}%")
        with ri2: st.metric("虧損機率",       f"{mc_res['loss_probability']:.1f}%")
        with ri3: st.metric("95% VaR",        f"{mc_res['var_95']:+.1f}%")
        with ri4: st.metric("95% CVaR",       f"{mc_res['cvar_95']:+.1f}%")

        # ── AI hedge advice ───────────────────────────────
        st.divider()
        st.subheader("🛡️ 市場層面避險建議")
        if st.button("🤖 生成避險策略", key="mc_hedge_btn"):
            with st.spinner("AI 分析中..."):
                macro_snap = get_macro_snapshot()
                vix_now, _ = fetch_vix()
                hedge_txt  = compare_with_crashes(
                    macro_snap, vix_now,
                    macro_snap.get("yield_curve_spread", {}).get("value", 0),
                    {"bullish_pct": 40, "bearish_pct": 40},
                )
            st.markdown(hedge_txt)
    elif mc_res:
        vix5, _ = fetch_vix()
        ys5 = get_macro_snapshot().get("yield_curve_spread", {}).get("value", 0)
        _ai_section(
            f"mc_{mc_ticker}", f"{mc_ticker} 模擬",
            analyze_mc_results,
            mc_ticker, mc_res["current_price"],
            mc_res["percentiles"]["P99"], mc_res["percentiles"]["P90"],
            mc_res["percentiles"]["P50"], mc_res["percentiles"]["P10"],
            mc_res["percentiles"]["P01"],
            mc_res["loss_probability"], mc_res["var_95"], mc_res["cvar_95"],
            vix5, ys5,
        )
    else:
        st.info("點擊「執行模擬」開始運算。")


# ══════════════════════════════════════════════════════════
#  TAB 6 — MY PORTFOLIO
# ══════════════════════════════════════════════════════════
with tab_portfolio:
    st.subheader("💼 我的投資組合模擬")

    show_glossary({
        "投資組合 (Portfolio)": "持有多支股票或ETF的組合，透過分散配置降低單一股票風險。",
        "權重 (Weight)": "每支股票佔總投資金額的百分比。例如 AAPL 30% 代表用30%的資金購買蘋果股票。",
        "P99 / P90 / P50 / P10 / P01": "模擬結果的百分位分佈。P99=最樂觀1%，P50=中位數，P01=最悲觀1%。",
        "虧損起始百分位": "從第幾個百分位開始出現虧損。例如「P35」代表有35%的模擬結果是虧損的。",
        "避險策略 (Hedging)": "透過配置防禦性資產（如黃金GLD、公債TLT）或反向部位來降低投資組合風險。",
        "ETF (指數股票型基金)": "追蹤特定指數的基金，如VOO追蹤S&P500，分散投資500家大型企業。",
        "分散化 (Diversification)": "投資不同行業、不同類型資產，避免單一事件造成全部虧損。",
        "期望報酬 (Expected Return)": "所有模擬結果的平均值，代表統計上最可能的報酬，但不保證一定發生。",
    }, "📖 本頁名詞說明（點擊展開）")


    PORTFOLIO_TEMPLATE = """# 格式：代碼, 權重%, 金額(USD)
AAPL, 25, 25000
MSFT, 20, 20000
NVDA, 15, 15000
JPM,  15, 15000
SPY,  15, 15000
GLD,  10, 10000"""

    col_input, col_hedge_input = st.columns(2)

    with col_input:
        st.markdown("**📥 原始投資組合**")
        portfolio_raw = st.text_area(
            "輸入持倉（代碼, 權重%, 金額）",
            value=st.session_state.get("portfolio_raw", PORTFOLIO_TEMPLATE),
            height=200,
            key="portfolio_raw_input",
            help="每行一支股票。格式：TICKER, 權重%, 投資金額(USD)",
        )
        st.session_state["portfolio_raw"] = portfolio_raw

    with col_hedge_input:
        st.markdown("**🛡️ 避險後投資組合**")
        hedge_raw = st.text_area(
            "輸入避險後持倉",
            value=st.session_state.get("hedge_raw", PORTFOLIO_TEMPLATE),
            height=200,
            key="hedge_raw_input",
            help="參考 AI 避險建議調整後的配置",
        )
        st.session_state["hedge_raw"] = hedge_raw

    run_btn = st.button("▶ 執行投資組合模擬（10,000次）",
                        type="primary", key="run_portfolio_btn")

    if run_btn:
        holdings_orig  = parse_portfolio_input(portfolio_raw)
        holdings_hedge = parse_portfolio_input(hedge_raw)

        valid_o, msg_o = validate_portfolio(holdings_orig)
        valid_h, msg_h = validate_portfolio(holdings_hedge)

        if not valid_o:
            st.error(f"原始組合錯誤：{msg_o}")
            st.stop()
        if not valid_h:
            st.error(f"避險組合錯誤：{msg_h}")
            st.stop()

        with st.spinner("執行蒙地卡羅模擬（需要約 30-60 秒）..."):
            mc_orig  = run_portfolio_mc(holdings_orig)
            mc_hedge = run_portfolio_mc(holdings_hedge)

        st.session_state["mc_orig"]        = mc_orig
        st.session_state["mc_hedge"]       = mc_hedge
        st.session_state["holdings_orig"]  = holdings_orig
        st.session_state["holdings_hedge"] = holdings_hedge

    mc_orig  = st.session_state.get("mc_orig")
    mc_hedge = st.session_state.get("mc_hedge")

    if mc_orig and mc_hedge:
        holdings_orig  = st.session_state.get("holdings_orig", {})
        holdings_hedge = st.session_state.get("holdings_hedge", {})

        # ── Donut charts ─────────────────────────────────
        d1, d2 = st.columns(2)
        with d1:
            st.plotly_chart(portfolio_donut(holdings_orig),  use_container_width=True)
        with d2:
            st.plotly_chart(portfolio_donut(holdings_hedge), use_container_width=True)

        # ── Comparison bar chart ─────────────────────────
        st.plotly_chart(
            percentile_comparison_chart(mc_orig, mc_hedge),
            use_container_width=True,
        )

        # ── Side-by-side percentile tables ───────────────
        st.subheader("📊 百分位詳細結果")
        t1, t2 = st.columns(2)
        total_o = mc_orig["total_value"]
        total_h = mc_hedge["total_value"]

        with t1:
            st.markdown("**原始配置**")
            df_o = format_percentile_table(mc_orig, total_o)
            st.dataframe(df_o, hide_index=True, use_container_width=True)
            st.metric("虧損機率",        f"{mc_orig['loss_probability']:.1f}%")
            st.metric("虧損起始百分位",  f"P{mc_orig['loss_starts_at']:.0f}")
            st.metric("95% VaR",         f"{mc_orig['var_95']:+.1f}%")

        with t2:
            st.markdown("**避險後配置**")
            df_h = format_percentile_table(mc_hedge, total_h)
            st.dataframe(df_h, hide_index=True, use_container_width=True)
            st.metric("虧損機率",        f"{mc_hedge['loss_probability']:.1f}%")
            st.metric("虧損起始百分位",  f"P{mc_hedge['loss_starts_at']:.0f}")
            st.metric("95% VaR",         f"{mc_hedge['var_95']:+.1f}%")

        # ── Distribution charts ───────────────────────────
        hist1, hist2 = st.columns(2)
        with hist1:
            st.plotly_chart(
                mc_distribution_chart(mc_orig["portfolio_returns"], "原始配置報酬分佈"),
                use_container_width=True,
            )
        with hist2:
            st.plotly_chart(
                mc_distribution_chart(mc_hedge["portfolio_returns"], "避險後配置報酬分佈"),
                use_container_width=True,
            )

        # ── AI hedge recommendation ────────────────────────
        st.divider()
        st.subheader("🤖 AI 個人化避險建議")
        if st.button("生成 AI 避險策略", key="personal_hedge_btn"):
            with st.spinner("AI 分析中..."):
                macro_snap = get_macro_snapshot()
                vix_now, _ = fetch_vix()
                hedge_advice = generate_hedge_strategy(
                    {t: (w, a) for t, (w, a) in holdings_orig.items()},
                    mc_orig, macro_snap, vix_now,
                )
            st.markdown(hedge_advice)
    elif mc_orig and mc_hedge:
        holdings6  = st.session_state.get("holdings_orig", {})
        vix6, _    = fetch_vix()
        _ai_section(
            "portfolio", "投資組合",
            analyze_portfolio,
            holdings6, mc_orig["total_value"],
            mc_orig["percentiles"]["P99"], mc_orig["percentiles"]["P90"],
            mc_orig["percentiles"]["P50"], mc_orig["percentiles"]["P10"],
            mc_orig["percentiles"]["P01"],
            mc_orig["loss_probability"], mc_orig["loss_starts_at"],
            mc_orig["var_95"], mc_orig["cvar_95"],
            mc_hedge["percentiles"]["P50"], mc_hedge["loss_probability"],
            vix6,
        )
    else:
        st.info("請輸入投資組合後點擊「執行模擬」。")


# ══════════════════════════════════════════════════════════
#  TAB 7 — SETTINGS
# ══════════════════════════════════════════════════════════
with tab_settings:
    st.subheader("⚙️ 設定")

    st.markdown("### 自定義觀察清單")
    watchlist_input = st.text_input(
        "輸入股票代碼（逗號分隔）",
        value=", ".join(st.session_state.get("watchlist", DEFAULT_TICKERS)),
        key="watchlist_input",
    )
    if st.button("更新觀察清單"):
        new_wl = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
        st.session_state["watchlist"] = new_wl
        st.success(f"已更新觀察清單：{len(new_wl)} 支股票")

    st.divider()
    st.markdown("### API 金鑰狀態")
    from config import (FRED_API_KEY, FINNHUB_API_KEY, NEWS_API_KEY,
                        GEMINI_API_KEY, REDDIT_CLIENT_ID, POLYGON_API_KEY)
    api_status = {
        "FRED API":        bool(FRED_API_KEY),
        "Finnhub":         bool(FINNHUB_API_KEY),
        "NewsAPI":         bool(NEWS_API_KEY),
        "Gemini (AI摘要)": bool(GEMINI_API_KEY),
        "Reddit (PRAW)":   bool(REDDIT_CLIENT_ID),
        "Polygon.io":      bool(POLYGON_API_KEY),
    }
    for name, ok in api_status.items():
        icon = "✅" if ok else "❌"
        st.markdown(f"{icon} **{name}** {'已設定' if ok else '未設定（請在 .env 中配置）'}")

    st.divider()
    st.markdown("### 模擬參數")
    st.info(f"""
- 模擬次數：**10,000 次**
- 預測期間：**21 個交易日（約一個月）**
- 歷史數據：**252 個交易日 + 四大崩盤時期**
- 歷史崩盤：
  - 1973-1974 石油危機
  - 2000-2003 網路泡沫
  - 2007-2009 金融海嘯
  - 2020 COVID-19 崩盤
""")

    st.divider()
    st.markdown("### 關於")
    st.markdown("""
**US Market Intelligence Dashboard**  
資料來源：yfinance · FRED · Finnhub · NewsAPI · Reddit · StockTwits · CBOE  
AI 摘要：OpenAI GPT-4o-mini  
框架：Python · Streamlit · Plotly  
部署：Streamlit Cloud (GitHub 自動部署)

> ⚠️ **免責聲明**：本工具僅供參考，不構成投資建議。投資有風險，請謹慎決策。
""")
