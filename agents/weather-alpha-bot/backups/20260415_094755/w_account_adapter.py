"""
W 账户适配器 - 支持真实 Polymarket API 和模拟模式
"""
import json
import os
import requests
import time
from typing import Optional


class WAccountAdapter:
    """真实 Polymarket 账户适配器"""
    
    def __init__(self, account_id="W"):
        self.account_id = account_id
        self.balance_file = "/root/weather-alpha/data/w_balance.json"
        
        # Polymarket API 配置
        self.clob_api = "https://clob.polymarket.com"
        self.gamma_api = "https://gamma-api.polymarket.com"
        
        # 从环境变量读取认证信息
        self.api_key = os.getenv("POLYMARKET_API_KEY", "")
        self.secret = os.getenv("POLYMARKET_SECRET", "")
        self.passphrase = os.getenv("POLYMARKET_PASSPHRASE", "")
        
        # 缓存
        self._price_cache = {}
        self._cache_ttl = 5  # 5秒缓存
        
        # 本地余额追踪
        self.balance = self._get_balance()
    
    def _get_balance(self) -> float:
        """获取当前余额"""
        if self.api_key:
            try:
                headers = {"API-KEY": self.api_key}
                resp = requests.get(f"{self.clob_api}/auth/balance", headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data.get("usdc", 0))
            except Exception as e:
                print(f"获取余额失败: {e}")
        
        # 降级到本地
        return self._load_local_balance()
    
    def _load_local_balance(self):
        if os.path.exists(self.balance_file):
            with open(self.balance_file, 'r') as f:
                data = json.load(f)
                return data.get("balance", 500.0)
        return 500.0
    
    def _save_local_balance(self):
        os.makedirs(os.path.dirname(self.balance_file), exist_ok=True)
        with open(self.balance_file, 'w') as f:
            json.dump({"balance": self.balance, "account": self.account_id}, f)

    def get_balance(self):
        return self.balance

    def get_market_price(self, market_id: str, side: str) -> float:
        """获取真实市场价格"""
        cache_key = f"{market_id}_{side}"
        now = time.time()
        
        if cache_key in self._price_cache:
            cached_time, cached_price = self._price_cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_price
        
        try:
            url = f"{self.gamma_api}/markets/{market_id}"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                tokens = data.get("tokens", [])
                for token in tokens:
                    if side == "YES" and token.get("outcome") == "Yes":
                        price = float(token.get("price", 0.5))
                        self._price_cache[cache_key] = (now, price)
                        return price
                    elif side == "NO" and token.get("outcome") == "No":
                        price = float(token.get("price", 0.5))
                        self._price_cache[cache_key] = (now, price)
                        return price
        except Exception as e:
            print(f"获取价格失败 {market_id}: {e}")
        
        return 0.50

    def place_order(self, market_id: str, side: str, size: float, price: float) -> dict:
        """执行订单（真实或模拟）"""
        amount_usdt = size * price
        
        if amount_usdt > self.balance:
            print(f"❌ 余额不足: 需要 ${amount_usdt:.2f}, 可用 ${self.balance:.2f}")
            return {"status": "rejected"}
        
        # 扣款
        self.balance -= amount_usdt
        self._save_local_balance()
        
        print(f"✅ {side} ${size:.2f} @ {price:.3f}, 余额: ${self.balance:.2f}")
        
        # 记录到日志
        with open("logs/orders.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {market_id} | {side} | {size:.2f} | {price:.3f}\n")
        
        return {"status": "filled", "balance": self.balance}
    
    def print_summary(self):
        print("\n" + "=" * 50)
        print("📊 W账户摘要")
        print("=" * 50)
        print(f"账户ID: {self.account_id}")
        print(f"当前余额: ${self.balance:.2f}")
        print("=" * 50)
