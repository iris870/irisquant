import asyncio
import aiohttp
import json
import logging
from datetime import datetime

class PolymarketAgent:
    def __init__(self):
        self.running = True
        self.logger = logging.getLogger("polymarket")
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.api_base = "https://clob.polymarket.com"
        self.gamma_api = "https://gamma-api.polymarket.com"

    async def fetch_active_markets(self, session):
        """Fetch currently active markets from Gamma API"""
        try:
            url = f"{self.gamma_api}/sampling-markets"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                self.logger.error(f"Failed to fetch markets: {resp.status}")
                return []
        except Exception as e:
            self.logger.error(f"Error fetching markets: {e}")
            return []

    async def strategy_loop(self):
        self.logger.info("Starting Polymarket strategy loop...")
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    markets = await self.fetch_active_markets(session)
                    if markets and len(markets) > 0:
                        # Log the first market for heartbeat/visibility
                        m = markets[0]
                        market_question = m.get('question', 'Unknown')
                        self.logger.info(f"Monitoring {len(markets)} markets. Top: {market_question}")
                    
                    # Simulation: Smart money following logic
                    # self.logger.info("following_smart_money: 0xWhaleAddress on BTC_PRICE_ABOVE_90K")
                    
                    await asyncio.sleep(30)
                except Exception as e:
                    self.logger.error(f"Error in Polymarket strategy loop: {e}")
                    await asyncio.sleep(10)

    async def cross_arb_loop(self):
        self.logger.info("Starting Cross-Arb loop...")
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    # Logic for cross-exchange arbitrage between Polymarket and Kalshi/Others
                    # Fixed: Use self.fetch_active_markets instead of undefined attribute
                    markets = await self.fetch_active_markets(session)
                    await asyncio.sleep(60)
                except Exception as e:
                    self.logger.error(f"Error in Cross-Arb loop: {e}")
                    await asyncio.sleep(10)

    async def run(self):
        self.logger.info("IrisQuant Polymarket Agent starting...")
        tasks = [
            asyncio.create_task(self.strategy_loop()),
            asyncio.create_task(self.cross_arb_loop())
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.running = False
            self.logger.info("Agent stopping...")

if __name__ == "__main__":
    agent = PolymarketAgent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass
