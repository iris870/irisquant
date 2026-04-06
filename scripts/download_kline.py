import requests
import pandas as pd
import time
import os
from datetime import datetime

def fetch_klines(symbol, interval, start_time, end_time, limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": limit
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def download_data(symbol, interval, start_date_str, end_date_str, output_path):
    start_ts = int(datetime.strptime(start_date_str, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date_str, "%Y-%m-%d").timestamp() * 1000)
    
    # Resume from existing file
    if os.path.exists(output_path):
        existing_df = pd.read_csv(output_path)
        if not existing_df.empty:
            last_ts = existing_df['timestamp'].max()
            start_ts = last_ts + 1
            print(f"Resuming {interval} from {datetime.fromtimestamp(start_ts/1000)}")

    all_data = []
    current_ts = start_ts
    count = 0

    while current_ts < end_ts:
        try:
            klines = fetch_klines(symbol, interval, current_ts, end_ts)
            if not klines:
                break
            
            # Format: [timestamp, open, high, low, close, volume, ...]
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Keep required fields
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Append to file immediately to save memory and handle crashes
            header = not os.path.exists(output_path)
            df.to_csv(output_path, mode='a', index=False, header=header)
            
            last_ts = df['timestamp'].iloc[-1]
            current_ts = last_ts + 1
            count += len(df)
            
            if count % 10000 == 0 or len(klines) < 1000:
                print(f"[{interval}] Downloaded {count} rows... Latest: {datetime.fromtimestamp(last_ts/1000)}")
            
            if len(klines) < 1000:
                break
                
            time.sleep(0.2) # Avoid rate limit
        except Exception as e:
            print(f"Error at {current_ts}: {e}")
            time.sleep(5)
            continue

    print(f"Completed {interval}: Total {count} rows saved to {output_path}")

if __name__ == "__main__":
    tasks = [
        ("BTCUSDT", "1h", "2021-04-01", "2026-04-03"),
        ("BTCUSDT", "5m", "2024-04-01", "2026-04-03"),
        ("BTCUSDT", "1m", "2024-04-01", "2026-04-03")
    ]
    
    os.makedirs("/root/irisquant/data/historical", exist_ok=True)
    
    for symbol, interval, start, end in tasks:
        path = f"/root/irisquant/data/historical/btc_usdt_{interval}.csv"
        download_data(symbol, interval, start, end, path)
