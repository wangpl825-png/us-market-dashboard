"""
scrapers/news_scraper.py
Collects news from RSS feeds, NewsAPI, Reddit (PRAW), and StockTwits.
"""

import feedparser
import requests
import praw
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from config import (
    RSS_FEEDS, NEWS_API_KEY, FINNHUB_API_KEY,
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT,
    REDDIT_SUBS, STOCKTWITS_TRENDING_URL, STOCKTWITS_STREAM_URL,
)


# ── RSS / NewsAPI ─────────────────────────────────────────

@st.cache_data(ttl=1800)
def fetch_rss_news(max_per_feed: int = 10) -> List[Dict]:
    """Fetch articles from all configured RSS feeds."""
    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                else:
                    pub_dt = datetime.now(timezone.utc)
                articles.append({
                    "source":    source,
                    "title":     entry.get("title", ""),
                    "summary":   _clean(entry.get("summary", "")),
                    "link":      entry.get("link", ""),
                    "published": pub_dt,
                })
        except Exception as e:
            print(f"[news] RSS error {source}: {e}")
    return sorted(articles, key=lambda x: x["published"], reverse=True)


@st.cache_data(ttl=1800)
def fetch_newsapi(query: str = "US stock market", page_size: int = 30) -> List[Dict]:
    """Fetch via NewsAPI free tier."""
    if not NEWS_API_KEY:
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q":        query,
            "language": "en",
            "sortBy":   "publishedAt",
            "pageSize": page_size,
            "apiKey":   NEWS_API_KEY,
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "source":    a.get("source", {}).get("name", "NewsAPI"),
                "title":     a.get("title", ""),
                "summary":   a.get("description", ""),
                "link":      a.get("url", ""),
                "published": pd.to_datetime(a.get("publishedAt")),
            })
        return articles
    except Exception as e:
        print(f"[news] NewsAPI error: {e}")
        return []


@st.cache_data(ttl=1800)
def fetch_finnhub_news(category: str = "general") -> List[Dict]:
    """Fetch market news from Finnhub."""
    if not FINNHUB_API_KEY:
        return []
    try:
        url = f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()
        articles = []
        for item in data[:40]:
            articles.append({
                "source":    item.get("source", "Finnhub"),
                "title":     item.get("headline", ""),
                "summary":   item.get("summary", ""),
                "link":      item.get("url", ""),
                "published": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ),
                "ticker":    item.get("related", ""),
                "sentiment": item.get("sentiment", None),
            })
        return articles
    except Exception as e:
        print(f"[news] Finnhub error: {e}")
        return []


@st.cache_data(ttl=1800)
def fetch_finnhub_ticker_news(ticker: str) -> List[Dict]:
    """Fetch company-specific news from Finnhub."""
    if not FINNHUB_API_KEY:
        return []
    try:
        from_dt = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        to_dt   = datetime.now().strftime("%Y-%m-%d")
        url = (
            f"https://finnhub.io/api/v1/company-news"
            f"?symbol={ticker}&from={from_dt}&to={to_dt}&token={FINNHUB_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        articles = []
        for item in data[:20]:
            articles.append({
                "source":    item.get("source", "Finnhub"),
                "title":     item.get("headline", ""),
                "summary":   item.get("summary", ""),
                "link":      item.get("url", ""),
                "published": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ),
            })
        return sorted(articles, key=lambda x: x["published"], reverse=True)
    except Exception as e:
        print(f"[news] Finnhub ticker news error {ticker}: {e}")
        return []


# ── Reddit ────────────────────────────────────────────────

@st.cache_data(ttl=1800)
def fetch_reddit_posts(limit: int = 30) -> List[Dict]:
    """Fetch hot posts from financial subreddits via PRAW."""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return _mock_reddit()
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            read_only=True,
        )
        posts = []
        for sub_name in REDDIT_SUBS:
            sub = reddit.subreddit(sub_name)
            for post in sub.hot(limit=limit // len(REDDIT_SUBS) + 2):
                posts.append({
                    "source":    f"r/{sub_name}",
                    "title":     post.title,
                    "summary":   post.selftext[:300] if post.selftext else "",
                    "link":      f"https://reddit.com{post.permalink}",
                    "published": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                    "score":     post.score,
                    "comments":  post.num_comments,
                    "upvote_ratio": post.upvote_ratio,
                })
        return sorted(posts, key=lambda x: x["score"], reverse=True)
    except Exception as e:
        print(f"[news] Reddit error: {e}")
        return _mock_reddit()


def _mock_reddit() -> List[Dict]:
    return [
        {
            "source": "r/investing",
            "title": "Reddit API not configured — add REDDIT_CLIENT_ID to .env",
            "summary": "See .env.example for setup instructions.",
            "link": "", "published": datetime.now(timezone.utc),
            "score": 0, "comments": 0, "upvote_ratio": 1.0,
        }
    ]


# ── StockTwits ────────────────────────────────────────────

@st.cache_data(ttl=1800)
def fetch_stocktwits_trending() -> List[Dict]:
    """Fetch trending tickers on StockTwits (no auth required)."""
    try:
        r = requests.get(STOCKTWITS_TRENDING_URL, timeout=10)
        data = r.json()
        symbols = data.get("symbols", [])
        return [
            {
                "ticker":       s.get("symbol", ""),
                "title":        s.get("title", ""),
                "watchlist_count": s.get("watchlist_count", 0),
            }
            for s in symbols
        ]
    except Exception as e:
        print(f"[news] StockTwits error: {e}")
        return []


@st.cache_data(ttl=900)
def fetch_stocktwits_stream(ticker: str, limit: int = 20) -> List[Dict]:
    """Fetch recent messages for a ticker from StockTwits."""
    try:
        url = STOCKTWITS_STREAM_URL.format(ticker=ticker)
        r = requests.get(url, timeout=10)
        data = r.json()
        messages = data.get("messages", [])
        results = []
        for m in messages[:limit]:
            sentiment = None
            entities = m.get("entities", {})
            sentiment_data = entities.get("sentiment", {})
            if sentiment_data:
                sentiment = sentiment_data.get("basic")
            results.append({
                "source":    "StockTwits",
                "title":     m.get("body", "")[:120],
                "summary":   m.get("body", ""),
                "link":      f"https://stocktwits.com/message/{m.get('id','')}",
                "published": pd.to_datetime(m.get("created_at")),
                "sentiment": sentiment,  # "Bullish" | "Bearish" | None
                "likes":     m.get("likes", {}).get("total", 0),
            })
        return results
    except Exception as e:
        print(f"[news] StockTwits stream error {ticker}: {e}")
        return []


# ── Aggregator ────────────────────────────────────────────

def get_all_news(include_reddit: bool = True) -> pd.DataFrame:
    """Merge all news sources into a single sorted DataFrame."""
    articles = fetch_rss_news()
    articles += fetch_newsapi()
    articles += fetch_finnhub_news()
    if include_reddit:
        reddit = fetch_reddit_posts()
        articles += reddit
    df = pd.DataFrame(articles)
    if df.empty:
        return df
    df["published"] = pd.to_datetime(df["published"], utc=True, errors="coerce")
    df = df.dropna(subset=["title"])
    df = df.drop_duplicates(subset=["title"])
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    return df


# ── Helpers ───────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip HTML tags from feed summaries."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    return clean[:400].strip()


def compute_news_sentiment(articles: List[Dict]) -> Dict:
    """
    Very simple keyword-based sentiment (no model required).
    Returns { bullish_pct, bearish_pct, neutral_pct, total }.
    """
    bullish_kw = {"surge", "rally", "gain", "rise", "bull", "strong",
                  "record", "growth", "beat", "profit", "recovery", "up"}
    bearish_kw = {"crash", "fall", "drop", "loss", "bear", "weak",
                  "recession", "decline", "miss", "fear", "risk", "down",
                  "inflation", "tariff", "default", "bankrupt"}
    counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    for a in articles:
        text = (a.get("title", "") + " " + a.get("summary", "")).lower()
        words = set(text.split())
        b_score = len(words & bullish_kw)
        n_score = len(words & bearish_kw)
        if b_score > n_score:
            counts["bullish"] += 1
        elif n_score > b_score:
            counts["bearish"] += 1
        else:
            counts["neutral"] += 1
    total = sum(counts.values()) or 1
    return {
        "bullish_pct":  round(counts["bullish"] / total * 100, 1),
        "bearish_pct":  round(counts["bearish"] / total * 100, 1),
        "neutral_pct":  round(counts["neutral"] / total * 100, 1),
        "total":        total,
    }
