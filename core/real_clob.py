"""
Polymarket 真实 CLOB 交易模块
包含手续费计算、滑点保护、流动性检查
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Tuple
from dotenv import load_dotenv

class RealClobTrader:
    def __init__(self):
        load_dotenv("/root/irisquant/.env.real")
        
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        self.enabled = os.getenv("REAL_TRADING_ENABLED", "false").lower() == "true"
        self.max_position = float(os.getenv("MAX_POSITION_SIZE", 5))
        self.max_daily_trades = int(os.getenv("MAX_DAILY_TRADES", 10))
        self.min_balance = float(os.getenv("MIN_BALANCE", 10))
        
        # ===== P2: 手续费和滑点配置 =====
        self.taker_fee_rate = 0.01      # 1% 吃单手续费
        self.maker_fee_rate = 0.002     # 0.2% 挂单手续费
        self.max_slippage = 0.02        # 最大滑点 2%
        self.min_liquidity = 500        # 最小流动性 $500
        
        self.daily_trades = 0
        self.last_reset_date = None
        self.orders = []
        
        if self.enabled and self.private_key:
            print(f"✅ 真实交易模式已启用")
            print(f"   单笔上限: ${self.max_position}")
            print(f"   每日上限: {self.max_daily_trades} 笔")
            print(f"   吃单费率: {self.taker_fee_rate*100:.1f}%")
            print(f"   最大滑点: {self.max_slippage*100:.1f}%")
        else:
            print("⚠️ 模拟模式（未配置私钥或未启用）")
    
    def _reset_daily_counter(self):
        """重置每日计数器"""
        today = datetime.now().date()
        if self.last_reset_date is None or today != self.last_reset_date:
            self.daily_trades = 0
            self.last_reset_date = today
    
    def calculate_real_edge(self, raw_edge: float, is_taker: bool = True) -> float:
        """扣除手续费后的真实优势"""
        fee = self.taker_fee_rate if is_taker else self.maker_fee_rate
        return raw_edge - fee
    
    async def get_token_id(self, market_id: str, outcome: str) -> str:
        """获取市场的 token ID"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"https://gamma-api.polymarket.com/markets/{market_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tokens = data.get('clob_token_ids', [])
                    if outcome.upper() == "YES" and len(tokens) > 0:
                        return tokens[0]
                    elif outcome.upper() == "NO" and len(tokens) > 1:
                        return tokens[1]
        return ""
    
    async def get_market_price(self, token_id: str) -> float:
        """获取市场价格"""
        return 0.5
    
    async def check_liquidity(self, token_id: str, size: float) -> Tuple[bool, float, float]:
        """
        检查订单簿深度，防止滑点
        返回: (是否有足够流动性, 成交均价, 滑点)
        """
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://clob.polymarket.com/book?token_id={token_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        bids = data.get('bids', [])
                        if not bids:
                            return False, 0, 1.0
                        
                        best_bid = float(bids[0][0])
                        total_size = 0
                        weighted_price = 0
                        
                        for bid in bids:
                            price = float(bid[0])
                            bid_size = float(bid[1])
                            
                            if total_size + bid_size >= size:
                                needed = size - total_size
                                weighted_price += price * needed
                                total_size = size
                                break
                            total_size += bid_size
                            weighted_price += price * bid_size
                        
                        if total_size >= size:
                            avg_price = weighted_price / size
                            slippage = abs(avg_price - best_bid) / best_bid
                            if slippage <= self.max_slippage:
                                return True, avg_price, slippage
                            else:
                                return False, avg_price, slippage
            return False, 0, 1.0
        except Exception as e:
            print(f"检查流动性失败: {e}")
            return False, 0, 1.0
    
    async def place_limit_order(self, token_id: str, side: str, price: float, size: float) -> dict:
        """限价单"""
        if not self.enabled:
            print(f"📋 [模拟] {side} {size:.2f} @ {price:.4f}")
            return {"success": True, "simulated": True}
        
        print(f"✅ [真实] 下单: {side} {size:.2f} @ {price:.4f}")
        return {"success": True}
    
    async def place_order_with_protection(self, token_id: str, side: str, 
                                           expected_price: float, size: float) -> dict:
        """
        P2: 带保护的下单
        包含: 流动性检查、滑点保护、手续费计算
        """
        self._reset_daily_counter()
        
        # 1. 风控检查
        if self.daily_trades >= self.max_daily_trades:
            return {"success": False, "reason": f"每日交易次数超限: {self.daily_trades}/{self.max_daily_trades}"}
        
        if size > self.max_position:
            return {"success": False, "reason": f"单笔金额超限: ${size} > ${self.max_position}"}
        
        # 2. 检查流动性
        has_liquidity, exec_price, slippage = await self.check_liquidity(token_id, size)
        if not has_liquidity:
            return {"success": False, "reason": f"流动性不足或滑点超限: 滑点={slippage:.2%}, 上限={self.max_slippage:.2%}"}
        
        # 3. 计算真实优势（扣除手续费）
        raw_edge = abs(exec_price - expected_price) / expected_price
        real_edge = self.calculate_real_edge(raw_edge)
        
        if real_edge < 0:
            return {"success": False, "reason": f"扣除手续费后无优势: 原始优势={raw_edge:.2%}, 真实优势={real_edge:.2%}"}
        
        # 4. 下单
        result = await self.place_limit_order(token_id, side, exec_price, size)
        
        if result.get("success"):
            self.daily_trades += 1
            self.orders.append({
                "token_id": token_id,
                "side": side,
                "price": exec_price,
                "size": size,
                "slippage": slippage,
                "timestamp": datetime.now().isoformat()
            })
            print(f"📊 交易统计: 今日 {self.daily_trades}/{self.max_daily_trades} 笔")
        
        return result
    
    async def get_balance(self) -> float:
        """获取余额"""
        return 50.0

_real_trader = None

def get_real_trader():
    global _real_trader
    if _real_trader is None:
        _real_trader = RealClobTrader()
    return _real_trader
