# 🇺🇸 US Market Intelligence Dashboard

> 美股財經資訊蒐集、分析、Monte Carlo 投資組合模擬的一站式儀表板

---

## ✨ 功能特色

| 模組 | 功能 |
|------|------|
| 📊 **總覽** | VIX、DXY、原油、殖利率曲線、恐懼貪婪指數、衰退風險評分 |
| 📈 **股票** | K線+技術指標（MACD/RSI/BB/ATR/VWAP）、個股新聞、快速MC預覽 |
| 🌐 **總體經濟** | FRED 14項指標、殖利率曲線、歷史崩盤比較、AI 分析 |
| 📰 **新聞情緒** | RSS+NewsAPI+Finnhub+Reddit+StockTwits 聚合、情緒分析、AI 摘要 |
| 🎲 **Monte Carlo** | 市場層面10,000次模擬、P99~P01分佈、VaR/CVaR |
| 💼 **投資組合** | 自定義持倉→MC模擬→避險前後對比→AI個人化建議 |

---

## 🚀 快速開始

### 1. Clone & 安裝

```bash
git clone https://github.com/YOUR_USERNAME/us-market-dashboard.git
cd us-market-dashboard
pip install -r requirements.txt
```

### 2. 設定 API Keys

```bash
cp .env.example .env
# 編輯 .env，填入你的 API Keys
```

**必要（免費）：**
- `FRED_API_KEY` → https://fred.stlouisfed.org/docs/api/api_key.html
- `FINNHUB_API_KEY` → https://finnhub.io/register

**選用（強化功能）：**
- `NEWS_API_KEY` → https://newsapi.org/register
- `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` → https://www.reddit.com/prefs/apps
- `OPENAI_API_KEY` → https://platform.openai.com/api-keys（啟用 AI 摘要）

> ⚡ 即使不設定任何 API Key，yfinance 仍可提供股票資料，大部分功能可運作。

### 3. 本地執行

```bash
streamlit run app.py
```

瀏覽器開啟 http://localhost:8501

---

## ☁️ 部署到 Streamlit Cloud（推薦，免費）

1. 將此 repo push 到 GitHub
2. 前往 https://share.streamlit.io → 連結你的 GitHub repo
3. 選擇 `app.py` 作為入口
4. 在 **Secrets** 頁面填入 API Keys（格式同 .env）
5. 完成！取得公開 URL，手機瀏覽器即可存取

---

## 📁 專案結構

```
us-market-dashboard/
├── app.py                    # Streamlit 主程式（7個分頁）
├── config.py                 # 集中設定（API Keys、參數、Watchlist）
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── config.toml           # 深色主題 + 行動裝置優化
├── scrapers/
│   ├── market_data.py        # yfinance + 技術指標（MACD/RSI/BB/ATR/VWAP）
│   ├── macro_data.py         # FRED 總體經濟 14項指標
│   └── news_scraper.py       # RSS/NewsAPI/Finnhub/Reddit/StockTwits
├── analysis/
│   └── summarizer.py         # GPT-4o-mini 新聞摘要 + 避險建議
├── simulation/
│   └── monte_carlo.py        # Monte Carlo 引擎（Block Bootstrap）
├── components/
│   └── charts.py             # 所有 Plotly 圖表
└── utils/
    └── helpers.py            # 通用工具函數
```

---

## 📊 技術指標清單

### 股票技術面
| 指標 | 說明 |
|------|------|
| MA 5/10/20/50/200 | 多週期移動平均線 |
| MACD + Signal + Histogram | 趨勢動能 |
| RSI (14) | 超買超賣判斷 |
| Bollinger Bands (%B) | 波動區間 |
| ATR (14) | 真實波動幅度 |
| Stochastic K/D | 短期超買超賣 |
| OBV | 成交量趨勢 |
| VWAP | 成交量加權均價 |

### 總體經濟面
| 指標 | 來源 |
|------|------|
| 失業率 | FRED UNRATE |
| CPI / Core CPI | FRED CPIAUCSL / CPILFESL |
| Core PCE | FRED PCEPILFE |
| 消費者信心 | FRED UMCSENT |
| Fed Funds Rate | FRED FEDFUNDS |
| 10Y / 2Y 殖利率 + 利差 | FRED DGS10/DGS2/T10Y2Y |
| M2 貨幣供給 | FRED M2SL |
| 實質 GDP 成長 | FRED A191RL1Q225SBEA |
| 住宅開工 | FRED HOUST |
| 零售銷售 | FRED RSXFS |
| 工業生產 | FRED INDPRO |
| VIX 恐慌指數 | yfinance ^VIX |
| 美元指數 DXY | yfinance DX-Y.NYB |
| WTI 原油 | yfinance CL=F |
| 恐懼貪婪指數 | alternative.me |
| Put/Call Ratio | CBOE 公開資料 |

---

## 🎲 Monte Carlo 方法說明

- **抽樣方法**：Block Bootstrap（區塊長度=5交易日），保留報酬自相關性
- **數據來源**：近252交易日 + 四大歷史崩盤時期（加權納入尾端風險）
- **崩盤時期**：1973-74石油危機、2000-03網路泡沫、2007-09金融海嘯、2020 COVID-19
- **結果呈現**：P99/P90/P75/P50/P25/P10/P01、VaR (95%)、CVaR (95%)、虧損機率

---

## ⚠️ 免責聲明

本工具僅供教育與研究用途，**不構成投資建議**。  
投資涉及風險，過去表現不代表未來結果。  
在做出任何投資決策前，請諮詢專業財務顧問。
