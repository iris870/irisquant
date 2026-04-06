#!/usr/bin/env python3
"""
Data Recorder - Accumulates historical data for RL training.
Unified management of market data, agent outputs, and trade records.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Configure logging if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataRecorder:
    """Unified Data Recorder"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize data recorder.
        
        Args:
            db_path: Database file path. Defaults to [ProjectRoot]/data/rl_data.db
        """
        if db_path is None:
            # Default to /root/irisquant/data/rl_data.db or relative to this file's parent's parent
            project_root = Path(__file__).resolve().parent.parent
            self.db_path = project_root / "data" / "rl_data.db"
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"DataRecorder initialized at: {self.db_path}")
    
    def _get_connection(self):
        """Get a database connection with dictionary factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. Market Data Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                timestamp INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                rsi REAL,
                ma20 REAL,
                ma50 REAL,
                volatility REAL,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """)
            
            # 2. Agent Output Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                output_type TEXT NOT NULL,
                value REAL,
                metadata TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """)
            
            # 3. Trade Records Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                strategy TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                position_size REAL,
                pnl REAL,
                market_state TEXT,
                status TEXT DEFAULT 'closed',
                open_time INTEGER,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """)
            
            # 4. System Events Table (For IrisRL/Monitoring)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                agent_name TEXT,
                details TEXT,
                resolved INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """)
            
            # 5. RL Experience Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS rl_experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                state TEXT,
                action TEXT,
                reward REAL,
                next_state TEXT,
                model_version TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """)
            
            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_timestamp ON market_data(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_timestamp ON agent_outputs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rl_timestamp ON rl_experiences(timestamp)")
            
            conn.commit()
        logger.debug("Database tables and indexes initialized")
    
    def record_market_data(self, data: Dict[str, Any]) -> bool:
        """Record market data (OHLCV + Indicators)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO market_data 
                (timestamp, symbol, open, high, low, close, volume, rsi, ma20, ma50, volatility)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('timestamp'),
                    data.get('symbol', 'BTC/USDT'),
                    data.get('open'),
                    data.get('high'),
                    data.get('low'),
                    data.get('close'),
                    data.get('volume'),
                    data.get('rsi'),
                    data.get('ma20'),
                    data.get('ma50'),
                    data.get('volatility')
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record market data: {e}")
            return False
    
    def record_agent_output(self, agent_name: str, output_type: str, 
                          value: float, metadata: Optional[Dict] = None) -> bool:
        """Record agent output (e.g., sentiment scores, predictions)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO agent_outputs (timestamp, agent_name, output_type, value, metadata)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    int(datetime.now().timestamp()),
                    agent_name,
                    output_type,
                    value,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
            logger.debug(f"Recorded {agent_name}.{output_type}: {value}")
            return True
        except Exception as e:
            logger.error(f"Failed to record agent output: {e}")
            return False
    
    def record_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Record trade details."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO trades (timestamp, strategy, direction, entry_price, 
                                 exit_price, position_size, pnl, market_state, status, open_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_data.get('timestamp', int(datetime.now().timestamp())),
                    trade_data.get('strategy'),
                    trade_data.get('direction'),
                    trade_data.get('entry_price'),
                    trade_data.get('exit_price'),
                    trade_data.get('position_size'),
                    trade_data.get('pnl'),
                    json.dumps(trade_data.get('market_state')) if isinstance(trade_data.get('market_state'), (dict, list)) else trade_data.get('market_state'),
                    trade_data.get('status', 'closed'),
                    trade_data.get('open_time')
                ))
                conn.commit()
            logger.info(f"Recorded trade: {trade_data.get('strategy')} Status={trade_data.get('status')}")
            return True
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            return False

    def update_trade(self, update_data: Dict[str, Any]) -> bool:
        """Update an open trade record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Find the latest open trade for this strategy
                cursor.execute("""
                UPDATE trades SET 
                exit_price = ?, 
                pnl = ?, 
                status = 'closed',
                timestamp = ?
                WHERE strategy = ? AND status = 'open'
                ORDER BY open_time DESC LIMIT 1
                """, (
                    update_data.get('exit_price'),
                    update_data.get('pnl'),
                    int(datetime.now().timestamp()),
                    update_data.get('strategy')
                ))
                conn.commit()
            logger.info(f"Updated trade: {update_data.get('strategy')} PnL={update_data.get('pnl')}")
            return True
        except Exception as e:
            logger.error(f"Failed to update trade: {e}")
            return False
    
    def record_system_event(self, event_type: str, agent_name: str, 
                           details: str) -> bool:
        """Record system events for audit/monitoring."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO system_events (timestamp, event_type, agent_name, details, resolved)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    int(datetime.now().timestamp()),
                    event_type,
                    agent_name,
                    details,
                    0
                ))
                conn.commit()
            logger.warning(f"System event: {event_type} on {agent_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to record system event: {e}")
            return False
    
    def record_rl_experience(self, state: Dict, action: str, 
                            reward: float, next_state: Dict,
                            model_version: str = "v1") -> bool:
        """Record RL (State, Action, Reward, NextState) transitions."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO rl_experiences (timestamp, state, action, reward, next_state, model_version)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    int(datetime.now().timestamp()),
                    json.dumps(state),
                    action,
                    reward,
                    json.dumps(next_state),
                    model_version
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to record RL experience: {e}")
            return False
    
    def get_latest_market_data(self, symbol: str = "BTC/USDT", 
                              limit: int = 100) -> List[Dict[str, Any]]:
        """Get latest market data as a list of dictionaries."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT * FROM market_data 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """, (symbol, limit))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return []

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate unrealized PnL based on open trades in database.
        
        Args:
            current_prices: Dict mapping symbol (e.g. 'BTC') to current float price.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Get all open trades
                cursor.execute("SELECT * FROM trades WHERE status = 'open'")
                open_trades = [dict(row) for row in cursor.fetchall()]
                
                total_unrealized_pnl = 0.0
                total_position_value = 0.0
                
                for trade in open_trades:
                    # Map strategy/pair to symbol in current_prices
                    # Basic mapping: if strategy or market_state contains 'BTC', use BTC price
                    symbol = 'BTC' # Default
                    price = current_prices.get(symbol, 0.0)
                    
                    if price > 0:
                        entry_price = trade.get('entry_price', 0.0)
                        size = trade.get('position_size', 0.0)
                        direction = trade.get('direction', 'long').lower()
                        
                        if direction == 'long':
                            pnl = (price - entry_price) * size
                        else: # short
                            pnl = (entry_price - price) * size
                            
                        total_unrealized_pnl += pnl
                        total_position_value += (price * size)
                
                return {
                    "unrealized_pnl": total_unrealized_pnl,
                    "position_value": total_position_value
                }
        except Exception as e:
            logger.error(f"Failed to calculate unrealized PnL: {e}")
            return {"unrealized_pnl": 0.0, "position_value": 0.0}

    def get_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trade history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []
    
    def cleanup_old_data(self, retention_days: int = 90) -> int:
        """Clean up data older than retention_days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cutoff = int(datetime.now().timestamp()) - (retention_days * 86400)
                
                total_deleted = 0
                tables = ['market_data', 'agent_outputs', 'trades', 'system_events', 'rl_experiences']
                
                for table in tables:
                    cursor.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
                    total_deleted += cursor.rowcount
                
                conn.commit()
            
            logger.info(f"Cleanup complete. Removed {total_deleted} rows across all tables.")
            return total_deleted
        except Exception as e:
            logger.error(f"Failed to cleanup data: {e}")
            return 0

    def close(self):
        """Placeholder for backward compatibility with older agent calls."""
        logger.debug("DataRecorder closed (no-op).")

# Global Singleton
_recorder: Optional[DataRecorder] = None

def get_recorder(db_path: Optional[str] = None) -> DataRecorder:
    """Get DataRecorder singleton instance."""
    global _recorder
    if _recorder is None:
        _recorder = DataRecorder(db_path)
    return _recorder

if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.DEBUG)
    recorder = get_recorder("data/test_rl_data.db")
    recorder.record_agent_output('test_agent', 'health_check', 1.0, {'status': 'ok'})
    print("Test record complete.")
