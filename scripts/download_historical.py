#!/usr/bin/env python3
"""
Historical Data Downloader
Downloads BTC historical OHLCV data from Binance for RL pre-training.
"""

import ccxt
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from core.data_recorder import get_recorder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataDownloader:
    """Historical Data Downloader"""
    
    def __init__(self, symbol: str = "BTC/USDT", data_dir: str = "data/historical"):
        self.symbol = symbol
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.data_dir = PROJECT_ROOT / data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.recorder = get_recorder()
    
    def download_ohlcv(self, timeframe: str = "1h", 
                      since: str = "2019-01-01", 
                      until: str = None) -> pd.DataFrame:
        """
        Download OHLCV data.
        """
        since_ts = self.exchange.parse8601(f"{since}T00:00:00Z")
        
        if until:
            until_ts = self.exchange.parse8601(f"{until}T23:59:59Z")
        else:
            until_ts = self.exchange.milliseconds()
        
        all_ohlcv = []
        current_ts = since_ts
        limit = 1000
        
        logger.info(f"Starting download: {self.symbol} {timeframe} from {since} to {until or 'now'}")
        
        while current_ts < until_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    self.symbol, timeframe, 
                    since=current_ts, 
                    limit=limit
                )
                
                if not ohlcv:
                    break
                
                all_ohlcv.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
                
                logger.info(f"Downloaded {len(all_ohlcv)} rows. Last: {datetime.fromtimestamp(ohlcv[-1][0]/1000)}")
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Download error: {e}")
                time.sleep(5)
                continue
        
        if not all_ohlcv:
            logger.error("No data downloaded.")
            return pd.DataFrame()

        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        
        df = self._add_indicators(df)
        
        filename = self.data_dir / f"{self.symbol.replace('/', '_')}_{timeframe}_{since}_{until or 'now'}.csv"
        df.to_csv(filename)
        logger.info(f"OK: Saved to {filename} ({len(df)} rows)")
        
        self._save_to_db(df, timeframe)
        
        return df
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators."""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma50'] = df['close'].rolling(window=50).mean()
        df['volatility'] = df['close'].pct_change().rolling(window=20).std() * 100
        
        return df
    
    def _save_to_db(self, df: pd.DataFrame, timeframe: str):
        """Save to database."""
        logger.info(f"Saving {len(df)} rows to DB...")
        count = 0
        for idx, row in df.iterrows():
            data = {
                'timestamp': int(row['timestamp'] / 1000), 
                'symbol': f"{self.symbol}_{timeframe}",
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'rsi': row.get('rsi'),
                'ma20': row.get('ma20'),
                'ma50': row.get('ma50'),
                'volatility': row.get('volatility')
            }
            if self.recorder.record_market_data(data):
                count += 1
        
        logger.info(f"OK: Saved {count} rows.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Download historical market data')
    parser.add_argument('--timeframe', default='1h', help='Timeframe (1m,5m,1h,4h,1d)')
    parser.add_argument('--since', default='2024-01-01', help='Start date YYYY-MM-DD')
    parser.add_argument('--until', default=None, help='End date YYYY-MM-DD')
    parser.add_argument('--symbol', default='BTC/USDT', help='Symbol')
    
    args = parser.parse_args()
    
    downloader = HistoricalDataDownloader(symbol=args.symbol)
    df = downloader.download_ohlcv(
        timeframe=args.timeframe,
        since=args.since,
        until=args.until
    )
    
    if not df.empty:
        print("
Download Complete!")
        print(f"Count: {len(df)} rows")
        print(f"Range: {df.index[0]} ~ {df.index[-1]}")
    else:
        print("
Download Failed.")


if __name__ == "__main__":
    main()
