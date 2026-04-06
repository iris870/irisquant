import ccxt
import pandas as pd
import time
from datetime import datetime
import os

def download_kline(symbol, timeframe, start_str, end_str, filename):
    exchange = ccxt.binance()
    start_ts = exchange.parse8601(start_str)
    end_ts = exchange.parse8601(end_str)
    
    # Check for existing file to resume
    all_data = []
    current_ts = start_ts
    
    if os.path.exists(filename):
        try:
            existing_df = pd.read_csv(filename)
            if not existing_df.empty:
                last_ts = existing_df['timestamp'].max()
                current_ts = int(last_ts) + exchange.parse_timeframe(timeframe) * 1000
                all_data = existing_df.values.tolist()
                print(f"Resuming {timeframe} from {datetime.fromtimestamp(current_ts/1000)}")
        except Exception as e:
            print(f"Error reading existing file: {e}, starting fresh.")

    print(f"Starting download for {symbol} {timeframe} from {datetime.fromtimestamp(current_ts/1000)} to {end_str}")
    
    count = 0
    while current_ts < end_ts:
        try:
            # Binance limit is 1000
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=1000)
            if not ohlcv:
                break
                
            all_data.extend(ohlcv)
            last_fetched_ts = ohlcv[-1][0]
            
            # Update current_ts for next loop
            current_ts = last_fetched_ts + exchange.parse_timeframe(timeframe) * 1000
            
            count += len(ohlcv)
            if count % 10000 < 1000: # Progress every ~10k
                print(f"[{timeframe}] Downloaded {len(all_data)} rows. Last TS: {datetime.fromtimestamp(last_fetched_ts/1000)}")
            
            # Save incrementally
            df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.to_csv(filename, index=False)
            
            time.sleep(0.2) # 200ms delay as requested
            
            if last_fetched_ts >= end_ts:
                break
                
        except Exception as e:
            print(f"Error fetching: {e}")
            time.sleep(5)
            continue

    print(f"Finished {timeframe}. Total rows: {len(all_data)}")
    return len(all_data)

if __name__ == "__main__":
    base_path = "/root/irisquant/data/historical"
    os.makedirs(base_path, exist_ok=True)
    
    configs = [
        ('1h', '2021-04-01T00:00:00Z', '2026-04-03T00:00:00Z'),
        ('5m', '2024-04-01T00:00:00Z', '2026-04-03T00:00:00Z'),
        ('1m', '2024-04-01T00:00:00Z', '2026-04-03T00:00:00Z'),
    ]
    
    for tf, start, end in configs:
        fname = f"{base_path}/btc_usdt_{tf}.csv"
        download_kline('BTC/USDT', tf, start, end, fname)
