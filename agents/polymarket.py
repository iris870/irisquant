import os
import sys
import logging

# Ensure irisquant root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
import aiohttp
from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange

# Setup standard logging to capture output in PM2 logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("polymarket")

class PolymarketAgent(BaseAgent):
    def __init__(self):
        super().__init__("polymarket")
        self.clob_base_url = "https://clob.polymarket.com"
        self.account_id = "POLYA_01"
        self.session = None
        self.monitored_markets = {}
        self.smart_money_list = []
        self.active_positions = {} # {market_id: position_info}

    async def _on_start(self):
        self.session = aiohttp.ClientSession()
        # 初始化聪明钱列表并包含测试地址
        self.smart_money_list = ["0xWhaleAddress"]
        # 启动三个策略循环
        self.tasks = [
            asyncio.create_task(self._smart_money_follower_loop()),
            asyncio.create_task(self._cross_market_arb_loop()),
            asyncio.create_task(self._probabilistic_edge_loop())
        ]
        self.logger.info("multi_strategy_engine_started")

    async def stop(self):
        self.running = False
        for task in self.tasks:
            task.cancel()
        if self.session:
            await self.session.close()
        await super().stop()

    # --- 策略一：概率套利 (Probabilistic Edge) ---
    async def _probabilistic_edge_loop(self):
        while self.running:
            try:
                # 简化逻辑用于测试
                m_id = "test_market_001"
                news_score = 0.7 
                onchain_score = 0.6
                hist_score = 0.5
                
                eval_prob = (news_score * 0.3) + (onchain_score * 0.2) + (hist_score * 0.5)
                price = 0.5
                edge = eval_prob - price
                
                if abs(edge) > 0.08:
                    side = "BUY_YES" if edge > 0 else "BUY_NO"
                    await self._execute_trade(m_id, side, abs(edge), "prob_edge")
                
                await asyncio.sleep(300) 
            except Exception as e:
                self.logger.error(f"Error in prob_edge_loop: {e}")
                await asyncio.sleep(10)

    # --- 策略二：聪明钱跟随 (Smart Money Follower) ---
    async def _smart_money_follower_loop(self):
        while self.running:
            try:
                # 模拟监听来自 onchain 的信号
                mock_signal = {
                    "address": "0xWhaleAddress",
                    "market_id": "0xBTC_PRICE_ABOVE_70K",
                    "side": "BUY_YES"
                }
                
                if mock_signal['address'] in self.smart_money_list:
                    self.logger.info(f"following_smart_money: {mock_signal['address']} on {mock_signal['market_id']}")
                    await self._execute_trade(mock_signal['market_id'], mock_signal['side'], 0.15, "smart_money")
                
                await asyncio.sleep(20)
            except Exception as e:
                self.logger.error(f"Error in smart_money_loop: {e}")
                await asyncio.sleep(5)

    # --- 策略三：跨市场套利 (Cross-Market Arb) ---
    async def _cross_market_arb_loop(self):
        while self.running:
            try:
                # 接入 Kalshi 数据 (通过新的 kalshi agent)
                kalshi_data = await self._get_agent_signal("kalshi", "all_prices")
                poly_data = await self.fetch_active_markets()
                
                for k_id, k_market in kalshi_data.items():
                    # 简单的文本模糊匹配或预设 ID 映射
                    p_id = self._match_market(k_market['title'], poly_data)
                    if p_id:
                        diff = abs(poly_data[p_id]['price'] - k_market['price'])
                        if diff > 0.03:
                            self.logger.info("arb_opportunity", diff=diff, market=k_market['title'])
                            # 执行对冲下单
                
                await asyncio.sleep(30)
            except Exception as e:
                self.logger.error(f"Error in cross_arb_loop: {e}")
                await asyncio.sleep(10)

    async def _get_agent_signal(self, agent_name, query):
        # 模拟跨 Agent 通信
        return 0.5 

    async def _execute_trade(self, market_id, side, confidence, strategy_name):
        # 实际下单逻辑（连接 CLOB API）
        self.logger.info("executing_trade", strategy=strategy_name, market=market_id, side=side)

    def _match_market(self, title, target_pool):
        # 基础 ID 映射或文本匹配
        return None

    async def fetch_events(self):
        """Fetch active markets from Polymarket CLOB."""
        try:
            if not self.session:
                return None
            
            async with self.session.get(f"{self.clob_base_url}/markets", params={"active": "true"}, timeout=10) as resp:
                if resp.status == 200:
                    try:
                        raw_data = await resp.json()
                    except Exception:
                        try:
                            raw_text = await resp.text()
                            self.logger.error(f"Failed to parse JSON, received text: {raw_text[:100]}")
                        except Exception:
                            self.logger.error("Failed to parse JSON and failed to read text")
                        return None
                    
                    if isinstance(raw_data, str):
                        self.logger.error(f"Unexpected string response: {raw_data[:100]}")
                        return None
                    
                    if not isinstance(raw_data, (dict, list)):
                        self.logger.error(f"Unexpected response type: {type(raw_data)}, data: {str(raw_data)[:100]}")
                        return None

                    if isinstance(raw_data, dict):
                        markets = raw_data.get("data", [])
                        if not isinstance(markets, list):
                            self.logger.error(f"Expected 'data' to be a list, got {type(markets)}")
                            return None
                    elif isinstance(raw_data, list):
                        markets = raw_data
                    else:
                        return None

                    crypto_markets = []
                    for m in markets:
                        if not isinstance(m, dict):
                            continue
                            
                        # Active market check
                        if not m.get("active") or m.get("closed"):
                            continue

                        title = (m.get("question") or m.get("description") or "").lower()
                        
                        # Broaden search to ensure we catch some active markets during testing
                        if any(kw in title for kw in ["bitcoin", "ethereum", "crypto", "btc", "eth", "trump", "election", "biden"]):
                            tokens = m.get("tokens", [])
                            if isinstance(tokens, list) and len(tokens) > 0:
                                # Often 'Yes' is the first token, but we should verify
                                for token in tokens:
                                    if not isinstance(token, dict):
                                        continue
                                    
                                    token_id = token.get("token_id")
                                    outcome = token.get("outcome", "")
                                    
                                    if token_id:
                                        crypto_markets.append({
                                            "id": token_id,
                                            "title": title,
                                            "outcome": outcome
                                        })
                                        # For now, just track one token per market to keep it simple
                                        break
                    
                    self.logger.info("markets_fetched", count=len(crypto_markets))
                    return crypto_markets
                else:
                    self.logger.warn(f"Polymarket API returned status {resp.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching Polymarket events: {e}")
            return None

    async def fetch_price(self, token_id):
        """Fetch current price for a token."""
        try:
            if not self.session or not token_id:
                return None
            
            async with self.session.get(f"{self.clob_base_url}/price?token_id={token_id}&side=buy", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        return float(data.get("price", 0))
                return None
        except Exception as e:
            self.logger.error(f"Error fetching price for {token_id}: {e}")
            return None

    async def _strategy_loop(self):
        self.logger.info("strategy_loop_started")
        while self.running:
            try:
                new_markets = await self.fetch_events()
                if new_markets:
                    self.monitored_markets = new_markets[:10]
                
                balance = await sim_exchange.fetch_balance(self.account_id)
                if isinstance(balance, dict) and "daily_pnl" in balance:
                    if balance.get("daily_pnl", 0) / 2000 < -0.10:
                        await self._emergency_exit("daily_loss_limit")
                        await asyncio.sleep(300)
                        continue

                for market in self.monitored_markets:
                    price = await self.fetch_price(market["id"])
                    if price and price < 0.30:
                        await self._place_bet(market, price)
                
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Error in Polymarket strategy loop: {e}")
                await asyncio.sleep(10)

    async def _place_bet(self, market, price):
        self.logger.info("bet_opportunity_found", market=market["title"], price=price)

    async def _emergency_exit(self, reason):
        self.logger.info("emergency_exit_triggered", reason=reason)

async import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.telegram import send_alert

def notify_arbitrage(market, profit):
    send_alert(f"⚖️ <b>[Polymarket]</b> Arbitrage Opportunity!
Market: {market}
Est. Profit: ${profit:,.2f}")

def main():
    agent = PolymarketAgent()
    try:
        await agent.start()
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
