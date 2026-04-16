
#!/usr/bin/env python3
"""
BTC 涨跌事件预测策略 v1.0 - 完整版
"""

import sys
sys.path.insert(0, "/root/irisquant")

import asyncio
import aiohttp
import logging
import json
from datetime import datetime
from typing import Optional, Tuple
from simulation.exchange_sim import sim_exchange


class BTCEventTrader:
    def __init__(self):
        self.running = True
        self.logger = self._setup_logger()
        
        self.gamma_api = "https://gamma-api.polymarket.com"
        self.clob_api = "https://clob.polymarket.com"
        
        self.min_edge = 0.05
        self.max_position = 100
        self.scan_interval = 30
        
        self.positions = {}
        self.last_prices = {}
        
        self.account_id = "C"
        
    def _setup_logger(self):
        logger = logging.getLogger("btc-event")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(handler)
        return logger
    
    async def get_binance_price(self, session):
        try:
            async with session.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data['price'])
        except Exception as e:
            self.logger.error(f"Binance error: {e}")
        return 0.0
    
    async def get_polymarket_btc_markets(self, session):
        try:
            url = f"{self.gamma_api}/markets?active=true&limit=50"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    markets = await resp.json()
                    btc_markets = []
                    for m in markets:
                        q = m.get('question', '').lower()
                        if 'btc' in q or 'bitcoin' in q:
                            prices_raw = m.get('outcomePrices', '[0.5, 0.5]')
                            if isinstance(prices_raw, str):
                                prices = json.loads(prices_raw)
                            else:
                                prices = prices_raw
                            yes_price = float(prices[0]) if prices else 0.5
                            btc_markets.append({
                                'id': m.get('id'),
                                'slug': m.get('slug'),
                                'question': m.get('question'),
                                'yes_price': yes_price,
                                'no_price': 1 - yes_price,
                                'volume': m.get('volume', 0),
                                'end_date': m.get('endDate')
                            })
                    return btc_markets
        except Exception as e:
            self.logger.error(f"Markets error: {e}")
        return []
    
    def calculate_technical_score(self, price_history):
        if len(price_history) < 20:
            return 0.5, 'neutral'
        recent = price_history[-10:]
        older = price_history[-20:-10]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if recent_avg > older_avg * 1.02:
            return 0.65, 'bullish'
        elif recent_avg < older_avg * 0.98:
            return 0.35, 'bearish'
        return 0.5, 'neutral'
    
    def calculate_position_size(self, edge, balance=1000):
        if edge <= self.min_edge:
            return 0
        kelly = edge * 0.5
        size = balance * kelly
        return min(size, self.max_position)
    
    async def execute_trade(self, market_slug, direction, size, price):
        """执行交易"""
        symbol = "YES" if direction == "YES" else "NO"
        result = await sim_exchange.create_order(self.account_id, symbol, "buy", size)
        if result["success"]:
            self.logger.info(f"📈 执行交易: {market_slug} | {direction} | ${size:.2f} @ {price:.3f}")
        else:
            self.logger.info(f"❌ 交易失败: {market_slug} | {direction} | 原因: {result}")
        return result["success"]
    
    async def analyze_market(self, session, market):
        btc_price = await self.get_binance_price(session)
        if btc_price == 0:
            return None
        
        q = market['question'].lower()
        is_up = 'above' in q or 'higher' in q or 'up' in q
        is_down = 'below' in q or 'lower' in q or 'down' in q
        
        mid = market['id']
        if mid not in self.last_prices:
            self.last_prices[mid] = []
        self.last_prices[mid].append(btc_price)
        if len(self.last_prices[mid]) > 100:
            self.last_prices[mid] = self.last_prices[mid][-100:]
        
        tech_score, trend = self.calculate_technical_score(self.last_prices[mid])
        
        if is_up and trend == 'bullish':
            edge = tech_score - market['yes_price']
            if edge > self.min_edge:
                return {
                    'market': market['slug'],
                    'direction': 'YES',
                    'price': market['yes_price'],
                    'edge': edge,
                    'size': self.calculate_position_size(edge),
                    'reason': 'BTC上涨趋势 + 技术看涨'
                }
        
        elif is_down and trend == 'bearish':
            edge = tech_score - market['no_price']
            if edge > self.min_edge:
                return {
                    'market': market['slug'],
                    'direction': 'NO',
                    'price': market['no_price'],
                    'edge': edge,
                    'size': self.calculate_position_size(edge),
                    'reason': 'BTC下跌趋势 + 技术看跌'
                }
        
        return None
    
    async def scan_loop(self):
        self.logger.info("=" * 50)
        self.logger.info("BTC 事件交易策略启动")
        self.logger.info(f"最小偏差: {self.min_edge*100:.0f}%")
        self.logger.info(f"单笔上限: ${self.max_position}")
        self.logger.info(f"扫描间隔: {self.scan_interval}s")
        self.logger.info("=" * 50)
        
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    markets = await self.get_polymarket_btc_markets(session)
                    btc_price = await self.get_binance_price(session)
                    
                    if not markets:
                        self.logger.info("未找到 BTC 相关市场")
                    else:
                        self.logger.info(f"发现 {len(markets)} 个 BTC 市场, BTC: ${btc_price:,.0f}")
                        
                        for market in markets:
                            signal = await self.analyze_market(session, market)
                            if signal and signal['size'] >= 5:
                                self.logger.info(f"🔔 信号: {signal['market']}")
                                self.logger.info(f"   方向: {signal['direction']} | 金额: ${signal['size']:.2f}")
                                self.logger.info(f"   偏差: {signal['edge']*100:.1f}% | 原因: {signal['reason']}")
                                
                                await self.execute_trade(
                                    signal['market'],
                                    signal['direction'],
                                    signal['size'],
                                    signal['price']
                                )
                    
                    await asyncio.sleep(self.scan_interval)
                    
                except Exception as e:
                    self.logger.error(f"扫描错误: {e}")
                    await asyncio.sleep(10)
    
    async def run(self):
        await self.scan_loop()
    
    def stop(self):
        self.running = False

if __name__ == "__main__":
    trader = BTCEventTrader()
    try:
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        trader.stop()
        print("BTC事件策略已停止")

