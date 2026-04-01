import os
import sys
import logging
import asyncio
import aiohttp
import sqlite3
from agents.base import BaseAgent
from thefuzz import fuzz

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("kalshi")

class KalshiAgent(BaseAgent):
    def __init__(self):
        super().__init__("kalshi")
        self.base_url = "https://api.kalshi.com/trade-api/v2"
        self.db_path = "/root/irisquant/storage/knowledge.db"
        self.session = None

    async def _on_start(self):
        self.session = aiohttp.ClientSession()
        self.logger.info("kalshi_agent_initialized")
        asyncio.create_task(self._price_broadcaster())

    async def _price_broadcaster(self):
        while self.running:
            try:
                # 1. 获取 Kalshi 市场
                kalshi_markets = await self.fetch_markets()
                # 2. 获取 Polymarket 市场 (模拟调用)
                poly_markets = [
                    {"id": "poly_btc_70k", "title": "Will Bitcoin reach $70,000 by April?"},
                    {"id": "poly_eth_4k", "title": "Will Ethereum hit $4,000?"}
                ]
                
                if kalshi_markets:
                    for km in kalshi_markets.get('markets', []):
                        k_title = km.get('title', '')
                        k_id = km.get('ticker', '')
                        
                        for pm in poly_markets:
                            score = fuzz.token_sort_ratio(k_title, pm['title'])
                            if score > 80:
                                self._save_mapping(pm['id'], k_id, pm['title'], score, "AUTO")
                                self.logger.info(f"match_found: {pm['title']} (Score: {score})")
                            elif 60 <= score <= 80:
                                self._save_mapping(pm['id'], k_id, pm['title'], score, "PENDING")
                                
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Error in kalshi broadcast: {e}")
                await asyncio.sleep(10)

    async def on_message(self, message):
        """处理手动指令"""
        content = message.get("content", "")
        if "bind event" in content:
            # 解析: bind event: polymarket_id=123, kalshi_id=456
            try:
                p_id = content.split("polymarket_id=")[1].split(",")[0].strip()
                k_id = content.split("kalshi_id=")[1].strip()
                self._save_mapping(p_id, k_id, "MANUAL_BIND", 100, "MANUAL")
                return {"status": "success", "message": f"Bound {p_id} to {k_id}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return None

    def _save_mapping(self, p_id, k_id, title, score, status):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO market_mapping (polymarket_id, kalshi_id, title, similarity, status)
            VALUES (?, ?, ?, ?, ?)
        """, (p_id, k_id, title, score, status))
        conn.commit()
        conn.close()

    async def fetch_markets(self):
        try:
            async with self.session.get(f"{self.base_url}/markets", params={"status": "open", "limit": 10}) as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            return {"markets": [{"ticker": "K_BTC_70", "title": "Bitcoin above $70,000?"}]}
        return None

    async def stop(self):
        if self.session:
            await self.session.close()
        await super().stop()

if __name__ == "__main__":
    agent = KalshiAgent()
    asyncio.run(agent.start())
