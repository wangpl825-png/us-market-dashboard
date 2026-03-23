"""
analysis/summarizer.py
Uses Google Gemini API to produce structured market summaries.
Falls back to plain text when API key is absent.
"""

import streamlit as st
import requests
import pandas as pd
from typing import List, Dict, Optional
from config import CRASH_PERIODS


def _gemini(prompt: str, max_tokens: int = 2000) -> str:
    """Call Gemini API, reading key fresh each time."""
    from config import GEMINI_API_KEY as _KEY
    if not _KEY:
        return ""
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={_KEY}"
        )
        system_msg = (
            "You are a professional financial analyst. "
            "Respond in Traditional Chinese (繁體中文). "
            "Be concise, factual, and data-driven."
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": system_msg + "\n\n" + prompt}],
                }
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            },
        }
        r = requests.post(url, json=payload, timeout=30)
        data = r.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        print(f"[summarizer] Gemini unexpected response: {data}")
        return ""
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"[summarizer] Gemini error: {e}")
        print(err)
        return f"[Gemini錯誤] {str(e)}"


@st.cache_data(ttl=3600)
def summarize_news(articles: List[Dict], category: str = "general") -> str:
    if not articles:
        return "目前無可用的新聞資料。"
    top = articles[:20]
    text_block = "\n".join(
        f"[{i+1}] {str(a.get('source',''))}: {str(a.get('title',''))}. {str(a.get('summary',''))[:200]}"
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
    result = _gemini(prompt, max_tokens=1500)
    if result:
        return result
    titles = [str(a.get("title", "")) for a in top[:5]]
    return "**最新頭條：**\n" + "\n".join(f"• {t}" for t in titles)


@st.cache_data(ttl=7200)
def compare_with_crashes(
    macro_snapshot: Dict,
    vix: float,
    yield_spread: float,
    news_sentiment: Dict,
) -> str:
    crash_descriptions = {
        "1973-1974 石油危機": "油價暴漲400%，通膨飆升至10%以上，Fed大幅升息，S&P500下跌約48%。",
        "2000-2003 網路泡沫": "科技股本益比泡沫破裂，NASDAQ下跌約78%，S&P500下跌約49%，失業率升至6%。",
        "2007-2009 金融海嘯": "次貸危機引發系統性金融風險，S&P500下跌約57%，失業率升至10%，信用市場凍結。",
        "2020 COVID-19 崩盤": "疫情衝擊，S&P500於33天內下跌34%，VIX飆至85，Fed緊急降息至0。",
    }
    unemployment = macro_snapshot.get("unemployment_rate", {}).get("value", "N/A")
    cpi = macro_snapshot.get("cpi_all_urban", {}).get("value", "N/A")
    fed_rate = macro_snapshot.get("fed_funds_rate", {}).get("value", "N/A")
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
    result = _gemini(prompt, max_tokens=2000)
    if result:
        return result
    return f"**歷史比較**\n\nVIX={vix:.1f}，殖利率利差={yield_spread:.2f}%\n\n{crash_block}\n\n建議：分散持股、增加防禦性配置（公債、黃金）、降低槓桿。"


@st.cache_data(ttl=3600)
def generate_hedge_strategy(
    portfolio: Dict,
    mc_results: Dict,
    macro_snapshot: Dict,
    vix: float,
) -> str:
    holdings_str = "\n".join(
        f"  - {ticker}: {weight*100:.1f}% (${amount:,.0f})"
        for ticker, (weight, amount) in portfolio.items()
    )
    p50 = mc_results.get("portfolio_p50", 0)
    p10 = mc_results.get("portfolio_p10", 0)
    p01 = mc_results.get("portfolio_p01", 0)
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
2. 🛡️ 具體避險策略
3. 📊 建議的調整後投資組合配置（百分比）
4. ⚡ 觸發進一步降低風險的警示條件
"""
    result = _gemini(prompt, max_tokens=1800)
    if result:
        return result
    return "請設定 GEMINI_API_KEY 以啟用 AI 避險分析。"


def summarize_ticker(ticker: str, news: List[Dict], tech_signal: str) -> str:
    if not news:
        return f"{ticker} 目前無相關新聞。技術訊號：{tech_signal}"
    titles = [str(a.get("title", "")) for a in news[:6]]
    titles_str = "\n".join(f"- {t}" for t in titles)
    prompt = f"""
股票代碼：{ticker}
技術分析訊號：{tech_signal}
最新新聞標題：
{titles_str}

請用2-3句話總結 {ticker} 目前的市場動態、基本面或技術面重點。
"""
    result = _gemini(prompt, max_tokens=200)
    return result if result else f"{ticker} | {tech_signal} | {titles[0] if titles else ''}"


def analyze_overview(
    vix: float, vix_prev: float,
    dxy: float, oil: float,
    yield_spread: float,
    fed_rate: float,
    unemployment: float,
    cpi: float,
    fear_greed: dict,
    pc_ratio: float,
    recession_score: int,
    recession_label: str,
) -> str:
    fg_val = fear_greed.get("value", 50) if fear_greed else 50
    fg_cls = fear_greed.get("classification", "N/A") if fear_greed else "N/A"
    pc_str = f"{pc_ratio:.2f}" if pc_ratio else "N/A"
    prompt = f"""
請根據以下即時市場數據，用繁體中文撰寫「市場綜合解讀」給一般投資人閱讀。

【當前關鍵數據】
- VIX 恐慌指數：{vix:.1f}（前日：{vix_prev:.1f}，變動：{vix-vix_prev:+.1f}）
- 美元指數 DXY：{dxy:.2f}
- WTI 原油：${oil:.1f}/桶
- 10Y-2Y 殖利率利差：{yield_spread:+.2f}%
- 聯邦基金利率：{fed_rate:.2f}%
- 失業率：{unemployment:.1f}%
- CPI 指數：{cpi:.1f}
- 恐懼貪婪指數：{fg_val}（{fg_cls}）
- Put/Call Ratio：{pc_str}
- 衰退風險評分：{recession_score}/100（{recession_label}）

請提供：
1. **整體市場氛圍**（2-3句，說明現在市場是偏樂觀/中性/緊張，以及為什麼）
2. **三大關鍵訊號**（最重要的3個數據點，說明其意義與對股市的影響）
3. **未來一個月走勢判斷**（給出明確方向：偏多/震盪/偏空，並說明主要理由）
4. **一般投資人應注意什麼**（1-2個具體建議）

語氣要像跟朋友解釋，讓沒有財經背景的人也看得懂。
"""
    result = _gemini(prompt, max_tokens=2200)
    if result:
        return result
    sentiment = "緊張" if vix > 25 else ("平靜" if vix < 15 else "中性")
    return f"**市場氛圍：{sentiment}**\n\nVIX={vix:.1f}，殖利率利差={yield_spread:+.2f}%，恐懼貪婪={fg_val}（{fg_cls}）\n\n➡️ 請設定 GEMINI_API_KEY 以啟用完整 AI 分析。"


def analyze_stock(
    ticker: str, company_name: str,
    close: float, pct_change: float,
    rsi: float, macd: float, macd_signal: float,
    bb_pct: float, atr: float,
    ma50: float, ma200: float,
    pe_ratio, forward_pe, beta,
    signal: str, news_titles: list,
) -> str:
    news_str = "\n".join(f"- {t}" for t in news_titles[:5]) if news_titles else "（無最新新聞）"
    prompt = f"""
請根據以下數據對 {ticker}（{company_name}）做出繁體中文的綜合分析。

【技術面數據】
- 收盤價：${close:.2f}（日漲跌：{pct_change:+.2f}%）
- RSI(14)：{rsi:.1f}（{'超買' if rsi>70 else '超賣' if rsi<30 else '中性'}）
- MACD：{macd:.3f}，信號線：{macd_signal:.3f}（{'金叉多頭' if macd>macd_signal else '死叉空頭'}）
- 布林通道 %B：{bb_pct:.2f}
- MA50：${ma50:.2f}，MA200：${ma200:.2f}（{'站上多頭排列' if close>ma200 else '跌破空頭排列'}）

【基本面數據】
- 本益比(PE)：{pe_ratio if pe_ratio else 'N/A'}
- 預測本益比(Forward PE)：{forward_pe if forward_pe else 'N/A'}
- Beta：{beta if beta else 'N/A'}
- 系統信號：{signal}

【最新新聞】
{news_str}

請提供：
1. **技術面判斷**（目前是多頭/空頭/盤整格局？）
2. **基本面評估**（估值是否合理？）
3. **新聞影響**（最新消息對股價有什麼可能影響？）
4. **短線操作建議**（未來1-2週，持有/觀望/減碼？說明理由）
"""
    result = _gemini(prompt, max_tokens=2200)
    if result:
        return result
    rsi_txt = "超買，注意回調" if rsi > 70 else ("超賣，關注反彈" if rsi < 30 else "中性")
    return f"**{ticker} 快速判讀**\n\n技術訊號：{signal} | RSI={rsi:.1f}（{rsi_txt}）\n\n➡️ 請設定 GEMINI_API_KEY 以啟用完整 AI 分析。"


def analyze_macro(
    unemployment: float, unemployment_chg: float,
    cpi: float, cpi_chg: float,
    fed_rate: float,
    yield_10y: float, yield_2y: float, yield_spread: float,
    m2: float, m2_chg_pct: float,
    consumer_conf: float,
    gdp_growth: float,
    recession_score: int,
) -> str:
    prompt = f"""
請根據以下美國總體經濟數據，用繁體中文為一般投資人撰寫綜合解讀。

【總體經濟指標】
- 失業率：{unemployment:.1f}%（月變動：{unemployment_chg:+.2f}%）
- CPI：{cpi:.1f}（月變動：{cpi_chg:+.2f}）
- 聯邦基金利率：{fed_rate:.2f}%
- 10年期公債殖利率：{yield_10y:.2f}%
- 2年期公債殖利率：{yield_2y:.2f}%
- 殖利率曲線利差(10Y-2Y)：{yield_spread:+.2f}%（{'倒掛' if yield_spread < 0 else '正常'}）
- M2 貨幣供給月變動：{m2_chg_pct:+.2f}%
- 消費者信心指數：{consumer_conf:.1f}
- 實質 GDP 成長率：{gdp_growth:.1f}%
- 衰退風險評分：{recession_score}/100

請提供：
1. **整體經濟健康度**（好/普通/危險，用2-3句解釋）
2. **通膨與利率分析**（目前通膨壓力如何？Fed 接下來可能做什麼？）
3. **衰退風險評估**（現在距離衰退有多遠？哪些指標最值得擔心？）
4. **對股市的影響**（總體經濟環境對股市是順風還是逆風？）
5. **與歷史的比較**（目前環境最像哪個歷史時期？）
"""
    result = _gemini(prompt, max_tokens=2500)
    if result:
        return result
    yc = "倒掛（歷史衰退前兆）" if yield_spread < 0 else "正常"
    return f"**總體經濟快速判讀**\n\n殖利率曲線{yc}（{yield_spread:+.2f}%），失業率{unemployment:.1f}%，Fed利率{fed_rate:.2f}%\n\n➡️ 請設定 GEMINI_API_KEY 以啟用完整 AI 分析。"


def analyze_news_sentiment(
    bullish_pct: float, bearish_pct: float, neutral_pct: float,
    total_articles: int,
    top_headlines: list,
    trending_tickers: list,
    vix: float,
) -> str:
    headlines_str = "\n".join(f"- {h}" for h in top_headlines[:8])
    trending_str = ", ".join(t.get("ticker", "") for t in trending_tickers[:8]) if trending_tickers else "N/A"
    prompt = f"""
請根據以下新聞情緒數據，用繁體中文撰寫市場情緒綜合解讀。

【情緒數據】
- 分析文章總數：{total_articles} 篇
- 偏多情緒：{bullish_pct:.1f}%
- 偏空情緒：{bearish_pct:.1f}%
- 中性情緒：{neutral_pct:.1f}%
- 目前 VIX：{vix:.1f}
- StockTwits 熱門股票：{trending_str}

【今日重要頭條】
{headlines_str}

請提供：
1. **市場情緒總結**（目前市場是恐慌/謹慎/中性/樂觀/貪婪？）
2. **主要新聞主題**（今天市場最關注的2-3個議題是什麼？）
3. **情緒與股市的關係**（目前情緒對短線股市走勢有什麼暗示？）
4. **反向指標提醒**（情緒是否走到極端？是否該考慮逆向操作？）
"""
    result = _gemini(prompt, max_tokens=2000)
    if result:
        return result
    dominant = "偏多" if bullish_pct > bearish_pct else ("偏空" if bearish_pct > bullish_pct else "中性")
    return f"**新聞情緒快速判讀**\n\n共分析 {total_articles} 篇文章，情緒{dominant}（多{bullish_pct:.0f}% / 空{bearish_pct:.0f}%）。VIX={vix:.1f}。\n\n➡️ 請設定 GEMINI_API_KEY 以啟用完整 AI 分析。"


def analyze_mc_results(
    ticker: str,
    current_price: float,
    p99: float, p90: float, p50: float, p10: float, p01: float,
    loss_prob: float,
    var_95: float, cvar_95: float,
    vix: float,
    yield_spread: float,
) -> str:
    prompt = f"""
請根據以下蒙地卡羅模擬結果，用繁體中文為一般投資人解讀數字的實際意義。

【模擬標的】{ticker}，當前價格 ${current_price:.2f}
【一個月模擬結果（10,000次）】
- P99（最樂觀1%）：{p99:+.2f}%
- P90：{p90:+.2f}%
- P50（中位數）：{p50:+.2f}%
- P10：{p10:+.2f}%
- P01（最悲觀1%）：{p01:+.2f}%
- 虧損機率：{loss_prob:.1f}%
- 95% VaR：{var_95:+.2f}%
- 95% CVaR：{cvar_95:+.2f}%

【市場環境】VIX={vix:.1f}，殖利率利差={yield_spread:+.2f}%

請提供：
1. **用人話解釋P50**（最可能的結果是賺多少或虧多少？）
2. **風險評估**（VaR和CVaR代表什麼？最壞的情境有多糟？）
3. **模擬結果是否合理**（根據目前市場環境，這個預測偏樂觀還是偏保守？）
4. **投資決策建議**（根據這些數字，現在是好的進場時機嗎？）
"""
    result = _gemini(prompt, max_tokens=2200)
    if result:
        return result
    dollar_p50 = current_price * p50 / 100
    return f"**模擬結果快速解讀**\n\nP50={p50:+.2f}%，虧損機率={loss_prob:.1f}%，VaR={var_95:+.1f}%\n\n➡️ 請設定 GEMINI_API_KEY 以啟用完整 AI 分析。"


def analyze_portfolio(
    holdings: dict,
    total_value: float,
    p99: float, p90: float, p50: float, p10: float, p01: float,
    loss_prob: float, loss_starts_at: float,
    var_95: float, cvar_95: float,
    hedge_p50: float, hedge_loss_prob: float,
    vix: float,
) -> str:
    holdings_str = "\n".join(
        f"  - {tk}: {w*100:.1f}% (${amt:,.0f})"
        for tk, (w, amt) in holdings.items()
    )
    improvement = hedge_p50 - p50
    risk_reduction = loss_prob - hedge_loss_prob
    prompt = f"""
請根據以下投資組合模擬結果，用繁體中文為投資人提供個人化的綜合分析與建議。

【投資組合】總資金：${total_value:,.0f}
{holdings_str}

【一個月蒙地卡羅模擬結果（原始配置）】
- P99：{p99:+.2f}%（+${total_value*p99/100:,.0f}）
- P50（最可能）：{p50:+.2f}%（{'+' if total_value*p50/100>=0 else ''}${total_value*p50/100:,.0f}）
- P01：{p01:+.2f}%（-${abs(total_value*p01/100):,.0f}）
- 虧損機率：{loss_prob:.1f}%（從 P{loss_starts_at:.0f} 開始虧損）
- VaR(95%)：{var_95:+.2f}%

【避險後配置比較】
- 避險後 P50：{hedge_p50:+.2f}%（改善：{improvement:+.2f}%）
- 避險後虧損機率：{hedge_loss_prob:.1f}%（降低：{risk_reduction:.1f}%）

【市場環境】VIX={vix:.1f}

請提供：
1. **投資組合健康度**（集中度是否過高？風險是否分散？）
2. **最大風險點**（哪一支股票最可能造成重大虧損？）
3. **避險效果評估**（避險配置是否真的有效降低風險？）
4. **具體改善建議**（最重要的1-2個調整是什麼？）
5. **心理準備**（最壞情況下可能損失多少，應該如何心理準備？）
"""
    result = _gemini(prompt, max_tokens=2500)
    if result:
        return result
    dollar_p50 = total_value * p50 / 100
    return f"**投資組合快速解讀**\n\nP50={p50:+.2f}%（${dollar_p50:,.0f}），虧損機率={loss_prob:.1f}%\n\n➡️ 請設定 GEMINI_API_KEY 以啟用完整 AI 分析。"
