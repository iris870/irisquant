import sys
sys.path.insert(0, "/root/irisquant")

#!/usr/bin/env python3
"""
完整套利策略 v1.1 - 修复跨平台套利单位换算问题
- Polymarket 内部价差套利（YES+NO<1）
- 跨平台套利（Polymarket vs Binance）- 修复版
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
import aiohttp
from simulation.exchange_sim import sim_exchange


class ArbitrageTrader:
    def __init__(self):
        self.running = True
        self.logger = self._setup_logger()
        
        # API 端点
        self.gamma_api = "https://gamma-api.polymarket.com"
        self.clob_api = "https://clob.polymarket.com"
        self.binance_api = "https://api.binance.com/api/v3"
        
        # 配置参数
        self.min_spread = 0.02      # 最小套利空间 2%
        self.max_position = 100     # 单边最大金额 USDC
        self.min_liquidity = 1000   # 最小流动性 USDC
        self.scan_interval = 30     # 扫描间隔（秒）
        
        # 统计
        self.opportunities_found = 0
        self.trades_executed = 0
        
        # 账户配置
        self.account_id = "C"
        
        # 默认目标价格映射（可根据实际市场调整）
        self.default_target_prices = {
            'bitcoin': 1_000_000,      # BTC to $1M
            'ethereum': 10_000,        # ETH to $10k
            'solana': 500,             # SOL to $500
        }
        
    def _setup_logger(self):
        logger = logging.getLogger("arbitrage")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(handler)
        return logger
    
    def _extract_target_price(self, question: str, slug: str = "") -> float:
        """
        从问题描述中提取目标价格
        支持格式: $1M, $1,000,000, $100k, $500 million 等
        """
        if not question:
            return 1_000_000  # 默认 $1M
        
        text = question.lower()
        
        # 查找加密货币关键词
        for crypto, default_price in self.default_target_prices.items():
            if crypto in text:
                base_price = default_price
                break
        else:
            base_price = 1_000_000
        
        # 尝试提取数字
        patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(?:million|m)',  # $1.5M
            r'\$(\d+(?:\.\d+)?)\s*(?:billion|b)',  # $2B
            r'\$(\d+(?:,\d+)*(?:\.\d+)?)',          # $1,000,000 or $1000000
            r'(\d+(?:\.\d+)?)\s*(?:million|m)',     # 1.5 million
            r'(\d+(?:\.\d+)?)\s*(?:billion|b)',     # 2 billion
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                num = float(match.group(1).replace(',', ''))
                if 'million' in text or 'm' in pattern and 'm' in text:
                    num *= 1_000_000
                elif 'billion' in text or 'b' in pattern and 'b' in text:
                    num *= 1_000_000_000
                return num
        
        return base_price
    
    async def fetch_markets(self, session: aiohttp.ClientSession) -> List[Dict]:
        """获取活跃市场"""
        try:
            url = f"{self.gamma_api}/markets?active=true&limit=100"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            self.logger.error(f"获取市场失败: {e}")
        return []
    
    async def get_binance_btc_price(self, session: aiohttp.ClientSession) -> float:
        """获取 Binance BTC 价格"""
        try:
            async with session.get(f"{self.binance_api}/ticker/price?symbol=BTCUSDT", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data['price'])
        except Exception as e:
            self.logger.error(f"获取 Binance 价格失败: {e}")
        return 0
    
    def calculate_internal_arbitrage(self, market: Dict) -> Optional[Dict]:
        """
        Polymarket 内部套利
        当 YES + NO < 1 - min_spread 时，存在套利机会
        """
        try:
            yes_price = float(market.get('price', 0))
            no_price = float(market.get('price_no', 0))
            
            if yes_price <= 0 or no_price <= 0:
                return None
            
            total = yes_price + no_price
            
            if total < 1 - self.min_spread:
                return {
                    'type': 'internal',
                    'market': market.get('slug'),
                    'question': market.get('question', '?')[:60],
                    'yes_price': yes_price,
                    'no_price': no_price,
                    'total': total,
                    'spread': 1 - total,
                    'estimated_profit': self.max_position * (1 - total)
                }
        except Exception as e:
            self.logger.error(f"计算内部套利失败: {e}")
        return None
    
    def calculate_cross_arbitrage(self, polymarket_price: float, binance_price: float, market: Dict) -> Optional[Dict]:
        """
        跨平台套利 - 修复版
        将 Polymarket 概率转换为目标价格，再与 Binance 价格对比
        """
        if polymarket_price <= 0 or binance_price <= 0:
            return None
        
        question = market.get('question', '')
        slug = market.get('slug', '')
        
        # 从市场描述中提取目标价格
        target_price = self._extract_target_price(question, slug)
        
        # 将 Polymarket 概率转换为预期价格
        polymarket_implied_price = polymarket_price * target_price
        
        # 合理性检查：预期价格不能太离谱
        if polymarket_implied_price < 1000 or polymarket_implied_price > target_price * 2:
            return None
        
        # 计算价格偏差
        price_diff = abs(polymarket_implied_price - binance_price)
        deviation = price_diff / binance_price
        
        # 只有当偏差超过阈值时才认为有套利机会
        if deviation > self.min_spread:
            direction = 'YES' if polymarket_implied_price < binance_price else 'NO'
            return {
                'type': 'cross',
                'market': market.get('slug'),
                'question': question[:60],
                'polymarket_price': polymarket_price,
                'polymarket_implied_price': polymarket_implied_price,
                'binance_price': binance_price,
                'target_price': target_price,
                'deviation': deviation,
                'direction': direction,
                'estimated_profit': self.max_position * deviation
            }
        return None
    
    async def execute_internal_arbitrage(self, opportunity: Dict):
        """执行内部套利（模拟盘）"""
        self.logger.info(f"🔄 执行内部套利: {opportunity['question']}")
        self.logger.info(f"   YES: {opportunity['yes_price']:.3f} | NO: {opportunity['no_price']:.3f} | 总和: {opportunity['total']:.3f}")
        self.logger.info(f"   套利空间: {opportunity['spread']*100:.2f}%")
        
        amount = self.max_position / 2
        result_yes = await sim_exchange.create_order(self.account_id, "YES", "buy", amount)
        result_no = await sim_exchange.create_order(self.account_id, "NO", "buy", amount)
        if result_yes["success"] and result_no["success"]:
            self.trades_executed += 1
            self.logger.info(f"内部套利成功: {opportunity['question']}")
        else:
            self.logger.info(f"内部套利失败: YES={result_yes}, NO={result_no}")
    
    async def execute_cross_arbitrage(self, opportunity: Dict):
        """执行跨平台套利（模拟盘）- 修复版"""
        self.logger.info(f"🔄 执行跨平台套利: {opportunity['question']}")
        self.logger.info(f"   Polymarket 概率: {opportunity['polymarket_price']:.3f} ({opportunity['polymarket_implied_price']:.0f} USDC)")
        self.logger.info(f"   Binance 价格: {opportunity['binance_price']:.2f} USDC")
        self.logger.info(f"   目标价格: ${opportunity['target_price']:,.0f}")
        self.logger.info(f"   价格偏差: {opportunity['deviation']*100:.2f}% | 方向: {opportunity['direction']}")
        
        amount = self.max_position
        side = "buy" if opportunity['direction'] == "YES" else "sell"
        result = await sim_exchange.create_order(self.account_id, "BTCUSDT", side, amount)
        if result["success"]:
            self.trades_executed += 1
            self.logger.info(f"跨平台套利成功: {opportunity['question']}")
        else:
            self.logger.info(f"跨平台套利失败: {result}")
    
    async def scan_loop(self):
        """主扫描循环"""
        self.logger.info("🚀 套利策略引擎启动")
        self.logger.info(f"   最小套利空间: {self.min_spread*100:.0f}%")
        self.logger.info(f"   单笔上限: ${self.max_position}")
        self.logger.info(f"   扫描间隔: {self.scan_interval} 秒")
        
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    # 获取 Binance BTC 价格
                    binance_price = await self.get_binance_btc_price(session)
                    if binance_price > 0:
                        self.logger.info(f"📊 Binance BTC 价格: ${binance_price:,.2f}")
                    
                    # 获取市场列表
                    markets = await self.fetch_markets(session)
                    if markets:
                        self.logger.info(f"🔍 扫描 {len(markets)} 个市场")
                        
                        internal_opps = []
                        cross_opps = []
                        
                        for market in markets[:100]:  # 限制扫描数量
                            # 内部套利
                            internal_opp = self.calculate_internal_arbitrage(market)
                            if internal_opp:
                                internal_opps.append(internal_opp)
                            
                            # 跨平台套利（只对有 BTC 相关的事件）
                            question = market.get('question', '').lower()
                            if 'bitcoin' in question or 'btc' in question:
                                polymarket_price = float(market.get('price', 0))
                                if polymarket_price > 0 and binance_price > 0:
                                    cross_opp = self.calculate_cross_arbitrage(polymarket_price, binance_price, market)
                                    if cross_opp:
                                        cross_opps.append(cross_opp)
                        
                        # 记录发现的机会
                        if internal_opps:
                            self.logger.info(f"💰 发现 {len(internal_opps)} 个内部套利机会")
                            for opp in internal_opps[:3]:
                                self.logger.info(f"   📊 {opp['question']}")
                                self.logger.info(f"      套利空间: {opp['spread']*100:.2f}%")
                                await self.execute_internal_arbitrage(opp)
                        
                        if cross_opps:
                            self.logger.info(f"🎯 发现 {len(cross_opps)} 个跨平台套利机会")
                            for opp in cross_opps[:3]:
                                self.logger.info(f"   📈 {opp['question']}")
                                self.logger.info(f"      偏差: {opp['deviation']*100:.2f}% | 方向: {opp['direction']}")
                                await self.execute_cross_arbitrage(opp)
                        
                        self.opportunities_found += len(internal_opps) + len(cross_opps)
                    
                    await asyncio.sleep(self.scan_interval)
                    
                except Exception as e:
                    self.logger.error(f"扫描循环错误: {e}")
                    await asyncio.sleep(self.scan_interval)
    
    async def stop(self):
        """停止套利引擎"""
        self.running = False
        self.logger.info("🛑 套利策略引擎停止")
        self.logger.info(f"📈 总计发现机会: {self.opportunities_found} | 执行交易: {self.trades_executed}")


async def main():
    trader = ArbitrageTrader()
    try:
        await trader.scan_loop()
    except KeyboardInterrupt:
        await trader.stop()


if __name__ == "__main__":
    asyncio.run(main())

