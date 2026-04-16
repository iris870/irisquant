#!/bin/bash
cd /root/weather-alpha
python3 -c "
from core.data_recorder import DataRecorder
r = DataRecorder()
s = r.get_statistics()
print('=' * 40)
print('策略运行统计')
print('=' * 40)
print(f'总预测次数: {s[\"total_predictions\"]}')
print(f'总订单数: {s[\"total_orders\"]}')
print(f'胜/负: {s[\"wins\"]}/{s[\"losses\"]}')
print(f'胜率: {s[\"win_rate\"]:.1%}' if s['win_rate'] else '胜率: N/A')
print(f'总盈亏: \${s[\"total_pnl\"]:.2f}')
"
