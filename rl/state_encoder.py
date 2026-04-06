#!/usr/bin/env python3
"""
RL 状态编码器 - 将系统状态转换为 RL 向量
"""

import numpy as np
from typing import Dict, List, Optional


class StateEncoder:
    """
    状态编码器
    将监控数据、Agent 状态、交易指标编码为固定维度向量
    """

    def __init__(self, state_dim: int = 64):
        """
        初始化编码器

        Args:
            state_dim: 输出向量维度
        """
        self.state_dim = state_dim

    def encode_system(self, metrics: Dict) -> List[float]:
        """
        编码系统指标

        Args:
            metrics: 包含 cpu_percent, memory_percent, disk_percent 的字典

        Returns:
            归一化后的特征列表
        """
        features = [
            metrics.get('cpu_percent', 0) / 100.0,
            metrics.get('memory_percent', 0) / 100.0,
            metrics.get('disk_percent', 0) / 100.0,
        ]
        return features

    def encode_agents(self, agents: List[Dict]) -> List[float]:
        """
        编码 Agent 状态

        Args:
            agents: Agent 状态列表，每个包含 status, cpu_percent, error_rate

        Returns:
            编码后的特征列表
        """
        status_map = {
            'running': 1.0,
            'stopped': 0.0,
            'error': -1.0,
            'unknown': 0.0
        }

        features = []
        for agent in agents[:10]:  # 最多处理 10 个 Agent
            status = agent.get('status', 'unknown')
            features.append(status_map.get(status, 0.0))
            features.append(agent.get('cpu_percent', 0) / 100.0)
            features.append(min(agent.get('error_rate', 0), 1.0))
        
        return features

    def encode_trades(self, trades: Dict) -> List[float]:
        """
        编码交易指标

        Args:
            trades: 包含 win_rate, daily_pnl, daily_trades 的字典

        Returns:
            编码后的特征列表
        """
        features = [
            min(max(trades.get('win_rate', 0), 0), 1.0),
            min(max(trades.get('daily_pnl', 0) / 10000.0, -1.0), 1.0),
            min(trades.get('daily_trades', 0) / 100.0, 1.0),
        ]
        return features

    def encode_combined(
        self,
        system_metrics: Dict,
        agents: List[Dict],
        trades_metrics: Dict
    ) -> np.ndarray:
        """
        组合编码所有状态

        Args:
            system_metrics: 系统指标
            agents: Agent 状态列表
            trades_metrics: 交易指标

        Returns:
            组合后的状态向量 (shape: state_dim,)
        """
        # 收集所有特征，先不进行填充，以免各子模块提前填 0 占据整个维度
        all_features = []
        all_features.extend(self.encode_system(system_metrics))
        all_features.extend(self.encode_agents(agents))
        all_features.extend(self.encode_trades(trades_metrics))
        
        # 最后统一进行填充/截断
        return self._pad(all_features)

    def _pad(self, features: List[float]) -> np.ndarray:
        """
        填充或截断到固定维度

        Args:
            features: 特征列表

        Returns:
            固定维度的 numpy 数组
        """
        arr = np.array(features, dtype=np.float32)
        if len(arr) < self.state_dim:
            arr = np.pad(arr, (0, self.state_dim - len(arr)), constant_values=0)
        return arr[:self.state_dim]


# 简单测试
if __name__ == "__main__":
    encoder = StateEncoder(state_dim=16)

    # 测试数据
    test_system = {
        'cpu_percent': 45.5,
        'memory_percent': 62.3,
        'disk_percent': 58.0
    }

    test_agents = [
        {'status': 'running', 'cpu_percent': 5.2, 'error_rate': 0.01},
        {'status': 'running', 'cpu_percent': 8.1, 'error_rate': 0.02},
        {'status': 'stopped', 'cpu_percent': 0, 'error_rate': 0.15},
    ]

    test_trades = {
        'win_rate': 0.55,
        'daily_pnl': 350.0,
        'daily_trades': 12
    }

    state_vec = encoder.encode_combined(test_system, test_agents, test_trades)
    print(f"状态向量维度: {state_vec.shape}")
    print(f"状态向量: {state_vec}")
    
    # 验证非零特征是否包含其中
    if np.any(state_vec > 0):
        print("✅ 状态编码器测试通过")
    else:
        print("❌ 警告：状态向量全为零")
