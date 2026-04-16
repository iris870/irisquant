import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

class DataRecorder:
    def __init__(self, data_dir="/root/weather-alpha/data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.predictions_file = os.path.join(data_dir, "predictions.json")
        self.orders_file = os.path.join(data_dir, "orders.csv")
        self.bias_file = os.path.join(data_dir, "city_bias.json")
        self.city_bias = self._load_bias()

    def record_prediction(self, strategy_name: str, market_id: str, 
                          predicted_prob: float, market_price: float,
                          features: Optional[Dict] = None):
        """记录一次预测"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy_name,
            "market_id": market_id,
            "predicted_prob": predicted_prob,
            "market_price": market_price,
            "edge": predicted_prob - market_price,
            "features": features or {}
        }
        predictions = self._load_predictions()
        predictions.append(record)
        self._save_predictions(predictions)

    def record_order(self, strategy_name: str, market_id: str, 
                     side: str, size: float, price: float,
                     predicted_prob: float, market_price: float):
        """记录一次下单"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "strategy": strategy_name,
            "market_id": market_id,
            "side": side,
            "size": size,
            "price": price,
            "predicted_prob": predicted_prob,
            "market_price": market_price,
            "edge": predicted_prob - market_price,
            "status": "pending"
        }
        file_exists = os.path.exists(self.orders_file)
        with open(self.orders_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=record.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(record)

    def update_order_outcome(self, market_id: str, actual_yes: int):
        """更新订单结算结果（YES获胜传1，NO获胜传0）"""
        if not os.path.exists(self.orders_file):
            return
        
        rows = []
        with open(self.orders_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['market_id'] == market_id and row['status'] == 'pending':
                    side = row['side']
                    is_win = (side == 'YES' and actual_yes == 1) or (side == 'NO' and actual_yes == 0)
                    row['status'] = 'win' if is_win else 'loss'
                    row['actual_outcome'] = str(actual_yes)
                rows.append(row)
        
        if rows:
            with open(self.orders_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

    def _load_predictions(self) -> List:
        if os.path.exists(self.predictions_file):
            with open(self.predictions_file, 'r') as f:
                return json.load(f)
        return []

    def _save_predictions(self, predictions):
        if len(predictions) > 10000:
            predictions = predictions[-10000:]
        with open(self.predictions_file, 'w') as f:
            json.dump(predictions, f, indent=2)

    def _load_bias(self) -> Dict:
        if os.path.exists(self.bias_file):
            with open(self.bias_file, 'r') as f:
                return json.load(f)
        return {}

    def get_statistics(self) -> Dict:
        orders = []
        if os.path.exists(self.orders_file):
            with open(self.orders_file, 'r') as f:
                reader = csv.DictReader(f)
                orders = list(reader)
        
        wins = len([o for o in orders if o.get('status') == 'win'])
        losses = len([o for o in orders if o.get('status') == 'loss'])
        total_pnl = 0.0
        for o in orders:
            if o.get('status') == 'win':
                size = float(o.get('size', 0))
                price = float(o.get('price', 0))
                total_pnl += size * (1 - price)
            elif o.get('status') == 'loss':
                total_pnl -= float(o.get('size', 0))
        
        return {
            "total_predictions": len(self._load_predictions()),
            "total_orders": len(orders),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / (wins + losses) if (wins + losses) > 0 else 0,
            "total_pnl": total_pnl
        }
