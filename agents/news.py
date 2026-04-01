import asyncio
import sys
import os
import aiohttp
import json
import feedparser
import re
from datetime import datetime
from collections import deque

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from core.rate_limiter import RateLimiter

class NewsAgent(BaseAgent):
    def __init__(self):
        super().__init__("news")
        # 五重防过载保护 (5-fold protection)
        self.rate_limiter = RateLimiter({
            "per_source": 0.033,   # ~1 request per 30s
            "global": 1.0,         # 1 req/s global limit
            "concurrency": 1,      # Max 1 concurrent request
            "queue_size": 5,       # Queue up to 5 requests
            "timeout": 30          # 30s timeout
        })
        self.news_api_url = "https://cryptocurrency.cv/api/news"
        self.latest_news = deque(maxlen=100) # Store more for deduplication
        self.sentiment_summary = {"positive": 0, "negative": 0, "neutral": 0, "score": 0.0}
        self.seen_titles = set()

        # RSS Sources configuration (Twitter via RSS.app/twitrss.me pattern)
        # Using a reliable pattern for RSS.app (proxied for stability if needed)
        self.rss_feeds = {
            "Binance": [
                "https://rss.app/feeds/twitter/binance.xml",
                "https://rss.app/feeds/twitter/BinanceHelp.xml",
                "https://rss.app/feeds/twitter/binancezh.xml",
                "https://rss.app/feeds/twitter/BinanceCN.xml"
            ],
            "BinanceCore": [
                "https://rss.app/feeds/twitter/cz_binance.xml",
                "https://rss.app/feeds/twitter/heyibinance.xml",
                "https://rss.app/feeds/twitter/NoahBPerlman.xml",
                "https://rss.app/feeds/twitter/RachelConlan.xml"
            ],
            "OKX": [
                "https://rss.app/feeds/twitter/okx.xml",
                "https://rss.app/feeds/twitter/OKX_Ventures.xml",
                "https://rss.app/feeds/twitter/OKXWeb3.xml",
                "https://rss.app/feeds/twitter/star_okx.xml"
            ],
            "BESA": [
                "https://rss.app/feeds/twitter/BESA_org.xml",
                "https://rss.app/feeds/twitter/BESA_Research.xml"
            ],
            "Media": [
                "https://rss.app/feeds/twitter/Cointelegraph.xml",
                "https://rss.app/feeds/twitter/CoinDesk.xml",
                "https://rss.app/feeds/twitter/CryptoPanic.xml"
            ],
            "Prediction": [
                "https://rss.app/feeds/twitter/Polymarket.xml"
            ]
        }

    async def _on_start(self):
        self.fetch_task = asyncio.create_task(self._background_fetcher())
        self.logger.info("NewsAgent started with 30s interval and RSS monitoring.")

    def _analyze_sentiment(self, text: str) -> str:
        text = text.lower()
        pos_words = ['up', 'surge', 'bull', 'gain', 'buy', 'positive', 'growth', 'record', 'high', 'rally', 'breakout', 'support', 'profit', 'ath', 'listing', 'launch']
        neg_words = ['down', 'drop', 'bear', 'loss', 'sell', 'negative', 'fall', 'crash', 'low', 'dump', 'resistance', 'liquidate', 'scam', 'hack', 'sec', 'ban', 'delist', 'maintenance']
        
        score = 0
        for word in pos_words:
            if word in text: score += 1
        for word in neg_words:
            if word in text: score -= 1
            
        if score > 0: return "positive"
        if score < 0: return "negative"
        return "neutral"

    def _clean_title(self, title: str) -> str:
        # Remove URLs and extra whitespace for better deduplication
        title = re.sub(r'http\S+', '', title)
        return " ".join(title.split()).lower()

    async def _fetch_rss(self, session: aiohttp.ClientSession):
        rss_news = []
        for category, urls in self.rss_feeds.items():
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            for entry in feed.entries[:5]: # Take top 5 from each
                                rss_news.append({
                                    "title": entry.title,
                                    "source": f"RSS:{category}",
                                    "link": entry.link,
                                    "published": getattr(entry, 'published', datetime.now().isoformat())
                                })
                        else:
                            self.logger.warning(f"RSS Status {response.status} for {url}")
                except Exception as e:
                    self.logger.error(f"RSS Fetch error for {url}: {str(e)}", exc_info=True)
        return rss_news

    async def _background_fetcher(self):
        cv_url = "https://cryptocurrency.cv/api/news"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            while self.running:
                try:
                    if await self.rate_limiter.acquire("news_fetch"):
                        all_raw_items = []
                        
                        # 1. Fetch CV News
                        try:
                            async with session.get(cv_url, timeout=15, ssl=False) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    raw_cv = data if isinstance(data, list) else (data.get("articles") or data.get("Data") or [])
                                    all_raw_items.extend([{"title": i.get("title") or i.get("body"), "source": "CV"} for i in raw_cv if isinstance(i, dict)])
                        except Exception as e:
                            self.logger.error(f"CV Fetch error: {e}")

                        # 2. Fetch RSS Feeds
                        rss_items = await self._fetch_rss(session)
                        all_raw_items.extend(rss_items)

                        if all_raw_items:
                            self._process_news_batch(all_raw_items)
                            self.logger.info(f"Synced {len(self.latest_news)} items. Score: {self.sentiment_summary['score']:.2f}")
                        
                        self.rate_limiter.release(True)
                except Exception as e:
                    self.logger.error(f"Fetcher loop error: {e}")
                
                await asyncio.sleep(30)

    def _process_news_batch(self, raw_items: list):
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        newly_processed = []
        
        for item in raw_items:
            raw_title = item.get("title")
            if not raw_title: continue
            
            clean_title = self._clean_title(raw_title)
            if clean_title in self.seen_titles:
                continue
                
            self.seen_titles.add(clean_title)
            sentiment = self._analyze_sentiment(raw_title)
            counts[sentiment] += 1
            
            entry = {
                "title": raw_title,
                "sentiment": sentiment,
                "source": item.get("source", "Unknown"),
                "time": datetime.now().isoformat()
            }
            newly_processed.append(entry)
            self.latest_news.appendleft(entry)

        # Update global summary based on the current sliding window (latest_news)
        if self.latest_news:
            total_counts = {"positive": 0, "negative": 0, "neutral": 0}
            for item in self.latest_news:
                total_counts[item["sentiment"]] += 1
            
            total = len(self.latest_news)
            self.sentiment_summary.update({
                **total_counts,
                "score": (total_counts["positive"] - total_counts["negative"]) / total
            })

        # Cleanup seen_titles to prevent memory leak
        if len(self.seen_titles) > 1000:
            self.seen_titles.clear()

    def get_news_sentiment(self) -> dict:
        return {
            "success": True,
            "data": {
                "summary": self.sentiment_summary,
                "latest_top_5": list(self.latest_news)[:5],
                "last_updated": datetime.now().isoformat()
            }
        }

async def run_agent():
    agent = NewsAgent()
    await agent.start()
    try:
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        pass
