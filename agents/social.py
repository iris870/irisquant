import os
import sys
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from agents.base import BaseAgent

logger = logging.getLogger(__name__)

class SocialAgent(BaseAgent):
    def __init__(self):
        super().__init__("social")
        self.trades_db_path = os.getenv("TRADES_DB_PATH", "/root/irisquant/knowledge.db")
        self.onchain_db_path = os.getenv("ONCHAIN_DB_PATH", "/root/irisquant/knowledge.db")
        self.running = True

    async def run(self):
        logger.info("Social agent started")
        await asyncio.gather(self._daily_report_loop(), self._whale_watcher_loop())

    async def _daily_report_loop(self):
        while self.running:
            now = datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target: target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            logger.info("Next daily report in %f hours" % (wait_seconds/3600))
            await asyncio.sleep(wait_seconds)
            try: self.generate_daily_report()
            except Exception as e: logger.error("Failed report: %s" % e)

    def generate_daily_report(self):
        try:
            conn = sqlite3.connect(self.trades_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            cursor.execute("SELECT agent, COUNT(*) as trades, SUM(pnl) as total_pnl, AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_rate FROM trades WHERE date(timestamp) = ? GROUP BY agent", (yesterday,))
            rows = cursor.fetchall()
            conn.close()
            if not rows: content = "No trades yesterday."
            else:
                total_pnl = sum(r["total_pnl"] for r in rows)
                content = f"Report {yesterday}: PnL ${total_pnl:.2f}"
            self._publish(content)
        except Exception as e:
            logger.error(f"Daily Report error: {e}", exc_info=True)

    async def _whale_watcher_loop(self):
        while self.running:
            try:
                conn = sqlite3.connect(self.onchain_db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades_raw'")
                if not cursor.fetchone():
                    logger.warning("Table 'trades_raw' not found in database. Skipping whale watch.")
                    conn.close()
                    await asyncio.sleep(60)
                    continue

                cursor.execute("SELECT * FROM trades_raw ORDER BY timestamp DESC LIMIT 1")
                row = cursor.fetchone()
                conn.close()
                if row and row["amount"] > 500000: 
                    msg = "Whale Alert! %s move: $%.2f" % (row["asset"], row["amount"])
                    self._publish(msg)
            except Exception as e: logger.error("Whale error: %s" % e)
            await asyncio.sleep(60)

    def _publish(self, content):
        logger.info("PUBLISHING TO TWITTER: %s" % content)
        # TODO: Implement real Twitter API call here
        # Example: twitter_client.create_tweet(text=content)

if __name__ == "__main__":
    agent = SocialAgent()
    asyncio.run(agent.run())