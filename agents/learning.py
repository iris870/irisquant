import asyncio
import sqlite3
from datetime import datetime, timedelta
import logging

class LearningAgent:
    def __init__(self, name):
        self.name = name
        self.db_path = "knowledge.db"
        self.logger = logging.getLogger(name)
        logging.basicConfig(level=logging.INFO)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT,
                symbol TEXT,
                side TEXT,
                amount REAL,
                price REAL,
                pnl REAL DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    async def run(self):
        self.logger.info("Learning agent started")
        while True:
            await self._daily_report_loop()
            await asyncio.sleep(3600 * 24)

    async def _daily_report_loop(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Simple example query
        cursor.execute("""
            SELECT agent, COUNT(*) as trade_count, 
                   AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_rate,
                   SUM(pnl) as total_pnl
            FROM trades
            WHERE date(timestamp) = ?
            GROUP BY agent
        """, (yesterday,))
        
        report = cursor.fetchall()
        conn.close()

        if not report:
            self.logger.info(f"No trades recorded for {yesterday}")
            return

        summary = f"Daily Report for {yesterday}:\n"
        for row in report:
            summary += f"- {row['agent']}: {row['trade_count']} trades, WinRate: {row['win_rate']:.2%}, PnL: {row['total_pnl']:.4f}\n"

        self.logger.info(f"Generated Daily Report:\n{summary}")

if __name__ == "__main__":
    agent = LearningAgent("learning")
    asyncio.run(agent.run())
