#!/usr/bin/env python3
import os
import json
import pandas as pd

data_dir = "/root/weather-alpha/data"
orders_file = os.path.join(data_dir, "orders.csv")
bias_file = os.path.join(data_dir, "adaptive_bias.json")

print("=" * 60)
print("策略分析报告")
print("=" * 60)

# 分析订单
if os.path.exists(orders_file):
    df = pd.read_csv(orders_file)
    print(f"\n📊 订单统计:")
    print(f"  总订单数: {len(df)}")
    
    if 'status' in df.columns:
        completed = df[df['status'].isin(['win', 'loss'])]
        if len(completed) > 0:
            wins = (completed['status'] == 'win').sum()
            losses = (completed['status'] == 'loss').sum()
            print(f"  已完成: {len(completed)}")
            print(f"  胜率: {wins/(wins+losses):.1%}")
            
            # 按策略统计
            print(f"\n📈 按策略统计:")
            for strategy in df['strategy'].unique():
                strategy_df = df[df['strategy'] == strategy]
                completed_s = strategy_df[strategy_df['status'].isin(['win', 'loss'])]
                if len(completed_s) > 0:
                    wins_s = (completed_s['status'] == 'win').sum()
                    print(f"  {strategy}: {wins_s}/{len(completed_s)} ({wins_s/len(completed_s):.1%})")
else:
    print("\n暂无订单数据，请继续运行策略")

# 分析偏差
if os.path.exists(bias_file):
    with open(bias_file, 'r') as f:
        bias = json.load(f)
    if bias:
        print(f"\n🎯 当前偏差:")
        for k, v in bias.items():
            print(f"  {k}: {v:.3f}")
    else:
        print("\n暂无偏差数据")
else:
    print("\n暂无偏差数据")

print("\n" + "=" * 60)
print("参数建议（基于现有数据）")
print("=" * 60)
print("  MIN_EDGE: 3% ~ 8%")
print("  KELLY_FRACTION: 0.2 ~ 0.4")
print("  建议继续积累数据以获得更精确的建议")
