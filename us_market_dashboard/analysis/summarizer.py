"""
analysis/summarizer.py
Uses OpenAI GPT-4o-mini to produce structured market summaries.
Falls back to extractive summarization when API key is absent.
"""

import openai
import streamlit as st
import pandas as pd
from typing import List, Dict, Optional
from config import OPENAI_API_KEY, CRASH_PERIODS

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    _client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    _client = None


def _gpt(prompt: str, max_tokens: int = 800) -> str:
    """Wrapper around OpenAI chat completion."""
    if not _client:
        return ""
    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional financial analyst. "
                        "Respond in Traditional Chinese (繁體中文) unless instructed otherwise. "
                        "Be concise, factual, and data-driven."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[summarizer] GPT error: {e}")
        return ""


@st.cache_data(ttl=3600)
def summarize_news(articles: List[Dict], category: str = "general") -> str:
    """
    Produce a structured summary for a list of news articles.
    Falls back to extractive top-5 titles if GPT unavailable.
    """
    if not articles:
        return "目前無可用的新聞資料。"

    # Build article list for prompt (max 20 to stay within token limits)
    top = articles[:20]
    text_block = "\n".join(
        f"[{i+1}] {a.get('source','')}: {a.get('title','')}. {a.get('summary','')[:200]}"
        for i, a in enumerate(top)
    )

    prompt = f"""
以下是最新的美股財經新聞（{category}類別）：

{text_block}

請根據以上資訊提供：
1. 📌 核心摘要（3-4句，重點市場動態）
2. 🔑 關鍵事件清單（最多5項，每項一句話）
3. 📊 市場情緒判斷（偏多/中性/偏空，並說明原因）
4. ⚠️ 需關注的風險因素（最多3項）
"""
    result = _gpt(prompt, max_tokens=600)
    if result:
        return result

    # Fallback: extractive
    titles = [a.get("title", "") for a in top[:5]]
    return "**最新頭條：**\n" + "\n".join(f"• {t}" for t in titles)


@st.cache_data(ttl=7200)
def compare_with_crashes(
    macro_snapshot: Dict,
    vix: float,
    yield_spread: float,
    news_sentiment: Dict,
) -> str:
    """
    Compare current macro conditions with historical crash periods
    and return a structured analysis.
    """
    crash_descriptions = {
        "1973-1974 石油危機":
            "油價暴漲400%，通膨飆升至10%以上，Fed大幅升息，S&P500下跌約48%。",
        "2000-2003 網路泡沫":
            "科技股本益比泡沫破裂，NASDAQ下跌約78%，S&P500下跌約49%，失業率升至6%。",
        "2007-2009 金融海嘯":
            "次貸危機引發系統性風融風險，S&P500下跌約57%，失業率升至10%，信用市場凍結。",
        "2020 COVID-19 崩盤":
            "疫情衝擊，S&P500於33天內下跌34%，VIX飆至85，Fed緊急降息至0。",
    }

    # Extract key current values
    unemployment = macro_snapshot.get("unemployment_rate", {}).get("value", "N/A")
    cpi          = macro_snapshot.get("cpi_all_urban",     {}).get("value", "N/A")
    fed_rate     = macro_snapshot.get("fed_funds_rate",    {}).get("value", "N/A")
    sentiment_str = f"偏多 {news_sentiment.get('bullish_pct',0):.0f}% / 偏空 {news_sentiment.get('bearish_pct',0):.0f}%"

    crash_block = "\n".join(f"- **{k}**: {v}" for k, v in crash_descriptions.items())

    prompt = f"""
目前美國市場環境：
- 失業率：{unemployment}%
- CPI指數：{cpi}
- 聯邦基金利率：{fed_rate}%
- VIX恐慌指數：{vix:.1f}
- 殖利率曲線利差(10Y-2Y)：{yield_spread:.2f}%
- 新聞市場情緒：{sentiment_str}

歷史崩盤背景：
{crash_block}

請進行比較分析：
1. 📉 與哪些歷史崩盤最為相似？（相似度評分1-10，並說明原因）
2. 🔍 目前市場的獨特性（與過去崩盤的最大差異）
3. 🛡️ 基於歷史經驗的避險建議（具體、可操作）
4. 📈 如果情況惡化，最可能的劇本
"""
    result = _gpt(prompt, max_tokens=800)
    if result:
        return result

    # Fallback
    return f"""
**歷史比較（基本模式）**

目前 VIX={vix:.1f}，殖利率利差={yield_spread:.2f}%

歷史參考：
{crash_block}

建議：分散持股、增加防禦性配置（公債、黃金）、降低槓桿。
"""


@st.cache_data(ttl=3600)
def generate_hedge_strategy(
    portfolio: Dict,
    mc_results: Dict,
    macro_snapshot: Dict,
    vix: float,
) -> str:
    """Generate personalized hedging recommendations based on portfolio + macro."""
    holdings_str = "\n".join(
        f"  - {ticker}: {weight*100:.1f}% (${amount:,.0f})"
        for ticker, (weight, amount) in portfolio.items()
    )
    p50  = mc_results.get("portfolio_p50",  0)
    p10  = mc_results.get("portfolio_p10",  0)
    p01  = mc_results.get("portfolio_p01",  0)
    loss_percentile = mc_results.get("loss_starts_at", "N/A")

    prompt = f"""
投資人目前持倉：
{holdings_str}

蒙地卡羅模擬結果（一個月後）：
- P50 報酬：{p50:+.2f}%
- P10 報酬：{p10:+.2f}%
- P01 報酬：{p01:+.2f}%
- 開始出現虧損的百分位：P{loss_percentile}

目前市場環境：
- VIX：{vix:.1f}（{'高波動' if vix > 25 else '正常'}）
- 殖利率曲線利差：{macro_snapshot.get('yield_curve_spread',{}).get('value','N/A')}%

請提供：
1. 🎯 整體風險評估（高/中/低，理由）
2. 🛡️ 具體避險策略（例如：買入Put選擇權/增加TLT/GLD配置/降低個股集中度）
3. 📊 建議的調整後投資組合配置（百分比）
4. ⚡ 觸發進一步降低風險的警示條件
"""
    result = _gpt(prompt, max_tokens=700)
    if result:
        return result
    return "請設定 OPENAI_API_KEY 以啟用 AI 避險分析。"


def summarize_ticker(ticker: str, news: List[Dict], tech_signal: str) -> str:
    """One-paragraph summary for a single stock."""
    if not news:
        return f"{ticker} 目前無相關新聞。技術訊號：{tech_signal}"
    titles = [a.get("title", "") for a in news[:6]]
    titles_str = "\n".join(f"- {t}" for t in titles)
    prompt = f"""
股票代碼：{ticker}
技術分析訊號：{tech_signal}
最新新聞標題：
{titles_str}

請用2-3句話總結 {ticker} 目前的市場動態、基本面或技術面重點。
"""
    result = _gpt(prompt, max_tokens=200)
    return result if result else f"{ticker} | {tech_signal} | {titles[0] if titles else ''}"
