import json
import os
import requests
import time
from datetime import datetime
from threading import Thread

class ResultTracker:
    def __init__(self, bias_corrector, data_dir="/root/weather-alpha/data"):
        self.bias_corrector = bias_corrector
        self.data_dir = data_dir
        self.predictions_file = os.path.join(data_dir, "predictions.json")
        self.orders_file = os.path.join(data_dir, "orders.csv")
        self.running = False
    
    def start(self, interval_seconds=300):
        """启动后台结果检查线程"""
        self.running = True
        
        def check_loop():
            while self.running:
                try:
                    self.check_all_markets()
                except Exception as e:
                    print(f"结果检查错误: {e}")
                time.sleep(interval_seconds)
        
        thread = Thread(target=check_loop, daemon=True)
        thread.start()
        print("📊 结果追踪器已启动，每5分钟检查一次市场结算")
    
    def stop(self):
        self.running = False
    
    def get_market_info(self, market_id):
        """从 Polymarket 获取市场信息"""
        try:
            # 尝试从市场ID提取信息
            # 格式如: NYC-PRECIP-2026-04-10
            parts = market_id.split('-')
            if len(parts) >= 3:
                return {
                    "slug": market_id,
                    "question": f"{parts[0]} 降雨预测",
                    "end_date": parts[-1] if len(parts[-1]) == 10 else None
                }
        except:
            pass
        return {"slug": market_id, "question": market_id, "end_date": None}
    
    def check_market_resolution(self, market_id):
        """检查市场是否已结算（简化版，通过API查询）"""
        try:
            # 使用 Polymarket Gamma API
            url = f"https://gamma-api.polymarket.com/markets/{market_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                closed = data.get("closed", False)
                outcome = data.get("outcome")
                return {
                    "resolved": closed,
                    "outcome": outcome  # "Yes" or "No"
                }
        except:
            pass
        
        # 如果API失败，检查是否超过结束日期
        info = self.get_market_info(market_id)
        if info.get("end_date"):
            try:
                end_date = datetime.strptime(info["end_date"], "%Y-%m-%d")
                if datetime.now() > end_date:
                    return {"resolved": True, "outcome": None}  # 已过期但未知结果
            except:
                pass
        
        return {"resolved": False, "outcome": None}
    
    def check_all_markets(self):
        """检查所有预测和订单的结算状态"""
        # 检查预测记录
        if os.path.exists(self.predictions_file):
            with open(self.predictions_file, 'r') as f:
                predictions = json.load(f)
            
            updated = False
            for pred in predictions:
                if pred.get("resolved"):
                    continue
                
                result = self.check_market_resolution(pred["market_id"])
                if result["resolved"]:
                    pred["resolved"] = True
                    if result["outcome"]:
                        actual_outcome = 1 if result["outcome"] == "Yes" else 0
                        pred["actual_outcome"] = actual_outcome
                        pred["was_correct"] = (actual_outcome == 1 and pred["predicted_prob"] > 0.5) or \
                                              (actual_outcome == 0 and pred["predicted_prob"] < 0.5)
                        
                        # 更新偏差修正
                        self.bias_corrector.update_bias(
                            pred["strategy"],
                            pred["market_id"],
                            pred["predicted_prob"],
                            actual_outcome
                        )
                        updated = True
                        print(f"✅ 市场已结算: {pred['market_id']} | 结果={'发生' if actual_outcome else '未发生'} | 预测={pred['predicted_prob']:.1%} | {'正确' if pred['was_correct'] else '错误'}")
            
            if updated:
                with open(self.predictions_file, 'w') as f:
                    json.dump(predictions, f, indent=2)
                
                resolved = [p for p in predictions if p.get("resolved")]
                if resolved:
                    correct = sum(1 for p in resolved if p.get("was_correct"))
                    print(f"📊 累计准确率: {correct}/{len(resolved)} = {correct/len(resolved)*100:.1f}%")
        
        # 检查订单记录
        if os.path.exists(self.orders_file):
            import csv
            with open(self.orders_file, 'r') as f:
                reader = csv.DictReader(f)
                orders = list(reader)
            
            # TODO: 更新订单结算状态
