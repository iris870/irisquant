import os
import json
import pandas as pd

data_dir = "/root/weather-alpha/data"
orders_file = os.path.join(data_dir, "orders.csv")

if os.path.exists(orders_file):
    df = pd.read_csv(orders_file)
    print("=== 策略分析报告 ===")
    print(f"总订单数: {len(df)}")
    if 'status' in df.columns:
        wins = (df['status'] == 'win').sum()
        losses = (df['status'] == 'loss').sum()
        print(f"胜率: {wins/(wins+losses):.1%}" if wins+losses>0 else "暂无结果")
else:
    print("暂无订单数据，请继续运行策略")
