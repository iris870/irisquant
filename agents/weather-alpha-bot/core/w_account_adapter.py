"""
Polymarket 真实交易适配器
使用官方 py-clob-client 和 polymarket-us SDK
"""
import os
import json
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta

# 官方 SDK
from py_clob_client.client import ClobClient
from py_clob_client.types import OrderArgs, Side, OrderType
from polymarket_us import PolymarketUS

class WAccountAdapter:
    """Polymarket 真实交易适配器（官方 SDK）"""
    
    def __init__(self, account_id: str = "W"):
        self.account_id = account_id
        
        # 从环境变量读取认证
        self.api_key = os.getenv("POLYMARKET_API_KEY", "")
        self.secret_key = os.getenv("POLYMARKET_SECRET_KEY", "")
        self.key_id = os.getenv("POLYMARKET_KEY_ID", "")  # polymarket-us 需要
        self.wallet_address = os.getenv("POLYMARKET_WALLET_ADDRESS", "")
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        
        # 安全开关
        self.trading_enabled = os.getenv("REAL_TRADING_ENABLED", "false").lower() == "true"
        self.max_position_usd = float(os.getenv("MAX_POSITION_USD", "20"))
        
        # 初始化官方客户端
        self._clob = None
        self._gamma = None
        
        if self.trading_enabled and self.private_key:
            self._init_clob_client()
            self._init_gamma_client()
        
        # 模拟余额文件
        self.balance_file = "/root/weather-alpha/data/w_balance.json"
        
        # 日志
        os.makedirs("logs", exist_ok=True)
        self._log(f"初始化完成 - 模式: {'真实交易' if self.trading_enabled else '模拟模式'}")
    
    def _init_clob_client(self):
        """初始化 CLOB 客户端"""
        try:
            self._clob = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=137,  # Polygon 主网
                private_key=self.private_key
            )
            self._log("CLOB 客户端初始化成功")
        except Exception as e:
            self._log(f"CLOB 客户端初始化失败: {e}")
    
    def _init_gamma_client(self):
        """初始化 Gamma API 客户端"""
        try:
            self._gamma = PolymarketUS(
                key_id=self.key_id,
                secret_key=self.secret_key
            )
            self._log("Gamma 客户端初始化成功")
        except Exception as e:
            self._log(f"Gamma 客户端初始化失败: {e}")
    
    def _log(self, msg: str):
        with open("logs/trading.log", "a") as f:
            f.write(f"{datetime.now().isoformat()} | {msg}\n")
    
    def get_balance(self) -> float:
        """获取余额"""
        # 真实模式：通过 Gamma API 获取
        if self.trading_enabled and self._gamma:
            try:
                balances = self._gamma.account.balances()
                usdc_balance = float(balances.get("usdc", 0))
                self._log(f"真实余额: ${usdc_balance:.2f}")
                return usdc_balance
            except Exception as e:
                self._log(f"获取余额失败: {e}")
        
        # 模拟余额
        if os.path.exists(self.balance_file):
            with open(self.balance_file, 'r') as f:
                data = json.load(f)
                return data.get("balance", 500.0)
        return 500.0
    
    def get_market_price(self, market_slug: str, side: str = "YES") -> float:
        """获取市场价格"""
        # 真实模式：通过 CLOB 获取
        if self.trading_enabled and self._clob:
            try:
                # 获取订单簿
                book = self._clob.get_order_book(market_slug)
                if side == "YES":
                    if book.bids and len(book.bids) > 0:
                        return float(book.bids[0].price)
                else:
                    if book.asks and len(book.asks) > 0:
                        return 1 - float(book.asks[0].price)
            except Exception as e:
                self._log(f"获取价格失败: {e}")
        
        # 降级：Gamma API
        try:
            import requests
            url = f"https://gamma-api.polymarket.com/markets/{market_slug}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                prices = data.get("outcomePrices", '["0.5","0.5"]')
                if isinstance(prices, str):
                    import ast
                    prices = ast.literal_eval(prices)
                return float(prices[0]) if side == "YES" else float(prices[1])
        except:
            pass
        
        return 0.5
    
    def place_order(self, market_slug: str, side: str, size: float, price: float) -> Dict:
        """下单"""
        amount = size * price
        current_balance = self.get_balance()
        
        if amount > current_balance:
            return {"status": "rejected", "reason": "insufficient_balance"}
        
        # 真实下单
        if self.trading_enabled and self._clob:
            return self._place_real_order(market_slug, side, size, price)
        
        # 模拟下单
        return self._place_simulated_order(market_slug, side, size, price)
    
    def _place_real_order(self, market_slug: str, side: str, size: float, price: float) -> Dict:
        """真实下单"""
        try:
            # 获取 token_id
            market_info = self._clob.get_market(market_slug)
            token_id = market_info.tokens[0] if side == "YES" else market_info.tokens[1]
            
            # 构建订单
            order_args = OrderArgs(
                token_id=token_id,
                side=Side.BUY,
                price=price,
                size=size,
                order_type=OrderType.GTC
            )
            
            # 下单
            order = self._clob.create_and_post_order(order_args, market_slug)
            
            self._log(f"真实下单成功: {side} {size} @ {price} - Order ID: {order.order_id}")
            return {"status": "filled", "order_id": order.order_id}
            
        except Exception as e:
            self._log(f"真实下单失败: {e}")
            return {"status": "error", "reason": str(e)}
    
    def _place_simulated_order(self, market_slug: str, side: str, size: float, price: float) -> Dict:
        """模拟下单"""
        amount = size * price
        current_balance = self.get_balance()
        
        if amount > current_balance:
            return {"status": "rejected", "reason": "insufficient_balance"}
        
        new_balance = current_balance - amount
        with open(self.balance_file, 'w') as f:
            json.dump({"balance": new_balance, "account": self.account_id}, f)
        
        self._log(f"[模拟] {side} ${size:.2f} @ {price:.3f}, 余额: ${new_balance:.2f}")
        
        return {"status": "filled", "balance": new_balance}
    
    def discover_markets(self, days_ahead: int = 3) -> List[Dict]:
        """自动发现温度市场"""
        discovered = []
        
        for days in range(1, days_ahead + 1):
            target_date = datetime.now() + timedelta(days=days)
            date_str = target_date.strftime("%B-%d-%Y").lower()
            event_slug = f"highest-temperature-in-nyc-on-{date_str}"
            
            try:
                import requests
                url = f"https://gamma-api.polymarket.com/events/{event_slug}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    event = resp.json()
                    markets = event.get('markets', [])
                    for market in markets:
                        discovered.append({
                            'slug': market.get('slug'),
                            'question': market.get('question'),
                            'condition_id': market.get('conditionId')
                        })
                    if markets:
                        self._log(f"发现市场 {event_slug}: {len(markets)} 个区间")
            except:
                pass
        
        return discovered
    
    def print_summary(self):
        print("\n" + "=" * 50)
        print("📊 Polymarket 账户")
        print("=" * 50)
        print(f"模式: {'🔴 真实交易' if self.trading_enabled else '🟡 模拟模式'}")
        print(f"余额: ${self.get_balance():.2f}")
        print(f"最大单笔: ${self.max_position_usd}")
        print("=" * 50)

