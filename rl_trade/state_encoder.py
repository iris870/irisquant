#!/usr/bin/env python3
"""
交易 RL 状态编码器 - 将市场数据编码为 RL 向量
"""

import numpy as np
from typing import Dict, List, Optional


class TradeStateEncoder:
    """
    交易状态编码器
    将市场数据、链上数据、情绪数据编码为固定维度向量
    """

    def __init__(self, state_dim: int = 128):
        """
        初始化编码器

        Args:
            state_dim: 输出向量维度
        """
        self.state_dim = state_dim

    def encode_market(self, market: Dict) -> List[float]:
        """
        编码市场数据

        Args:
            market: 包含价格、RSI、MA、波动率等

        Returns:
            特征列表
        """
        features = []

        # 价格特征 (归一化到 0-1 左右，假设 BTC 上限 100k)
        close = market.get('close', 0) or 0
        features.append(close / 100000.0)

        # 技术指标
        features.append(market.get('rsi', 50) / 100.0)
        features.append(market.get('volatility', 0) / 100.0)

        # 均线关系 (相对位置)
        ma20 = market.get('ma20', close) or close
        ma50 = market.get('ma50', close) or close
        
        if ma20 > 0:
            features.append((close - ma20) / ma20)
        else:
            features.append(0.0)
            
        if ma50 > 0:
            features.append((close - ma50) / ma50)
        else:
            features.append(0.0)

        # 成交量 (归一化)
        volume = market.get('volume', 0) or 0
        features.append(min(volume / 1000000.0, 1.0))

        return features

    def encode_onchain(self, onchain: Dict) -> List[float]:
        """
        编码链上数据

        Args:
            onchain: 包含活跃地址、交易所流量等

        Returns:
            特征列表
        """
        features = []

        # 活跃地址
        active = onchain.get('active_addresses', 0) or 0
        features.append(min(active / 2000000.0, 1.0))

        # 交易所净流量 (正=流入，负=流出)
        exchange_flow = onchain.get('exchange_flow', 0) or 0
        features.append(min(max(exchange_flow / 50000.0, -1.0), 1.0))

        # 算力
        hashrate = onchain.get('hashrate', 0) or 0
        features.append(min(hashrate / 1000.0, 1.0))

        return features

    def encode_sentiment(self, sentiment: Dict) -> List[float]:
        """
        编码情绪数据

        Args:
            sentiment: 包含新闻评分、社交评分等

        Returns:
            特征列表
        """
        features = []

        # 新闻情绪
        news = sentiment.get('news_score', 0.5) or 0.5
        features.append(min(max(news, 0), 1.0))

        # 社交媒体情绪
        social = sentiment.get('social_score', 0.5) or 0.5
        features.append(min(max(social, 0), 1.0))

        # 恐惧贪婪指数
        fg = sentiment.get('fear_greed', 50) or 50
        features.append(fg / 100.0)

        return features

    def encode_position(self, position: Dict) -> List[float]:
        """
        编码当前持仓

        Args:
            position: 包含仓位大小、浮盈等

        Returns:
            特征列表
        """
        features = []

        # 当前仓位系数 (-1.0 到 1.0)
        size = position.get('current_size', 0) or 0
        features.append(min(max(size, -1.0), 1.0))

        # 未实现盈亏
        pnl = position.get('unrealized_pnl', 0) or 0
        features.append(min(max(pnl / 0.5, -1.0), 1.0))

        # 持仓时长 (归一化到秒，上限 2 小时)
        duration = position.get('position_duration', 0) or 0
        features.append(min(duration / 7200.0, 1.0))

        return features

    def encode_combined(
        self,
        market: Dict,
        onchain: Dict,
        sentiment: Dict,
        position: Dict
    ) -> np.ndarray:
        """
        组合编码所有状态

        Args:
            market: 市场数据
            onchain: 链上数据
            sentiment: 情绪数据
            position: 持仓数据

        Returns:
            组合后的状态向量
        """
        features = []
        features.extend(self.encode_market(market))
        features.extend(self.encode_onchain(onchain))
        features.extend(self.encode_sentiment(sentiment))
        features.extend(self.encode_position(position))

        arr = np.array(features, dtype=np.float32)
        if len(arr) < self.state_dim:
            arr = np.pad(arr, (0, self.state_dim - len(arr)), constant_values=0)
        return arr[:self.state_dim]


# 测试脚本
if __name__ == "__main__":
    encoder = TradeStateEncoder(state_dim=64)

    # 模拟测试数据
    test_market = {
        'close': 65000,
        'rsi': 65,
        'volatility': 25,
        'ma20': 64200,
        'ma50': 63800,
        'volume': 1200000
    }

    test_onchain = {
        'active_addresses': 950000,
        'exchange_flow': -1500,
        'hashrate': 650
    }

    test_sentiment = {
        'news_score': 0.7,
        'social_score': 0.65,
        'fear_greed': 72
    }

    test_position = {
        'current_size': 0.3,
        'unrealized_pnl': 0.05,
        'position_duration': 3600
    }

    state = encoder.encode_combined(test_market, test_onchain, test_sentiment, test_position)
    print(f"状态向量维度: {state.shape}")
    print(f"前 15 个特征值: {state[:15]}")
    
    assert state.shape[0] == 64, "维度校验失败"
    assert state[0] == 0.65, "价格归一化校验失败"
    
    print("✅ 交易 RL 状态编码器测试成功")
