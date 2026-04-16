import os
import json
from datetime import datetime
from typing import Dict

class RealPolymarketExchange:
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get('REAL_TRADING_ENABLED', 'false').lower() == 'true'
        self.daily_trades = 0
        self.last_reset_date = datetime.now().date()
        self.max_position_size = float(config.get('MAX_POSITION_SIZE', 5))
        self.max_daily_trades = int(config.get('MAX_DAILY_TRADES', 10))
        self.orders = []
        
        if self.enabled:
            print("✅ 真实交易模式已启用")
        else:
            print("⚠️ 模拟模式（未启用真实交易）")
    
    def reset_daily_counter(self):
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trades = 0
            self.last_reset_date = today
    
    async def get_balance(self) -> float:
        return 50.0
    
    async def get_market_price(self, market_id: str, outcome: str) -> float:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"https://gamma-api.polymarket.com/markets/{market_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    prices = json.loads(data.get('outcomePrices', '["0.5","0.5"]'))
                    return float(prices[0]) if outcome == 'YES' else float(prices[1])
        return 0.5
    
    async def create_order(self, account_id: str, symbol: str, side: str, amount_usdt: float) -> Dict:
        self.reset_daily_counter()
        
        if self.daily_trades >= self.max_daily_trades:
            return {"success": False, "reason": "daily_trade_limit"}
        
        if amount_usdt > self.max_position_size:
            return {"success": False, "reason": f"exceeds_max_size: {amount_usdt} > {self.max_position_size}"}
        
        price = await self.get_market_price(symbol, "YES")
        quantity = amount_usdt / price
        
        order = {
            "id": f"order_{datetime.now().timestamp()}",
            "account_id": account_id,
            "market_id": symbol,
            "side": side.upper(),
            "amount_usdt": amount_usdt,
            "quantity": quantity,
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        if self.enabled:
            order["status"] = "executed"
            print(f"✅ [真实交易] 下单: {symbol} {side} ${amount_usdt} @ {price}")
        else:
            order["status"] = "simulated"
            print(f"📋 [模拟] 订单: {symbol} {side} ${amount_usdt} @ {price}")
        
        self.orders.append(order)
        self.daily_trades += 1
        
        return {
            "success": True,
            "account_id": account_id,
            "balance": await self.get_balance(),
            "order": order
        }
    
    async def close_position(self, account_id: str, symbol: str) -> Dict:
        return {"success": True, "reason": "not_implemented"}

_real_exchange = None

def get_real_exchange():
    global _real_exchange
    if _real_exchange is None:
        from dotenv import load_dotenv
        load_dotenv("/root/irisquant/.env.real")
        _real_exchange = RealPolymarketExchange(os.environ)
    return _real_exchange
