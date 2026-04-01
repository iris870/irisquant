import asyncio
import time
import random
from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange

class BTCRollingAgent(BaseAgent):
    def __init__(self):
        super().__init__("btc-rolling")
        self.account_id = "A"
        self.symbol = "BTC/USDT"
        self.position_ratio = 0.25
        self.last_trade = 0

    async def _on_start(self):
        asyncio.create_task(self._strategy_loop())

    async def _strategy_loop(self):
        while self.running:
            await asyncio.sleep(60)
            if time.time() - self.last_trade < 300:
                continue
            balance = await sim_exchange.fetch_balance(self.account_id)
            if balance["daily_pnl"] / 10000 < -0.05:
                continue
            price = sim_exchange.get_price(self.symbol)
            sentiment = random.choice(["bullish", "neutral", "bearish"])
            if sentiment == "bullish" and not self._has_position():
                await self._trade("buy", balance["total"], price)

    def _has_position(self):
        return sim_exchange.accounts[self.account_id].position is not None

    async def _trade(self, side: str, balance: float, price: float):
        amount = balance * self.position_ratio
        result = await sim_exchange.create_order(self.account_id, self.symbol, side, amount)
        if result["success"]:
            self.last_trade = time.time()
            self.logger.info("trade_executed", side=side, amount=amount, price=price)

async def main():
    import asyncio
    agent = BTCRollingAgent()
    await agent.start()
    try:
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await agent.stop()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
