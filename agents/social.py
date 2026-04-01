import asyncio
import random
import sqlite3
import logging
from datetime import datetime, timedelta
from agents.base import BaseAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("social-agent")

class SocialAgent(BaseAgent):
    def __init__(self):
        super().__init__("social")
        self.db_path = "/root/irisquant/knowledge.db"
        self.onchain_db_path = "/root/irisquant/storage/knowledge.db"
        self.last_posted_whale_trade = None

    async def _on_start(self):
        # Schedule various loops
        self.tasks = [
            asyncio.create_task(self._daily_report_loop()),      # 8:00 AM
            asyncio.create_task(self._whale_watcher_loop()),     # Real-time
            asyncio.create_task(self._market_analysis_loop()),   # 9:00, 14:00, 20:00
            asyncio.create_task(self._engagement_loop())         # 3 times a week
        ]
        logger.info("SocialAgent started with all optimization loops.")

    async def _daily_report_loop(self):
        """Daily report at 08:00 AM"""
        while self.running:
            now = datetime.now()
            # Target 08:00:00
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target = target.replace(day=now.day + 1)
            
            wait_seconds = (target - now).total_seconds()
            logger.info(f"Daily report scheduled in {wait_seconds/3600:.2f} hours")
            await asyncio.sleep(wait_seconds)
            
            await self._post_daily_report()

    async def _post_daily_report(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT agent, COUNT(*) as trades, SUM(pnl) as total_pnl,
                       AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_rate
                FROM trades WHERE date(timestamp) = ? GROUP BY agent
            """, (yesterday,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                content = "☕️ 昨日市场静默，IrisQuant 正在积蓄力量。准备迎接今日波动！ #IrisQuant #Trading"
            else:
                total_pnl = sum(r['total_pnl'] for r in rows)
                avg_win = sum(r['win_rate'] for r in rows) / len(rows)
                emoji = "🚀" if total_pnl > 0 else "📉"
                
                content = (
                    f"{emoji} IrisQuant 每日战报 ({yesterday})

"
                    f"💰 总盈亏: ${total_pnl:,.2f}
"
                    f"🎯 平均胜率: {avg_win:.1%}

"
                    "核心表现：
"
                )
                for r in rows:
                    content += f"• {r['agent']}: {r['trades']}笔 | {r['win_rate']:.0%}胜率
"
                
                content += "
#IrisQuant #BTC #TradingRobot #Web3"
            
            self._publish(content)
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")

    async def _whale_watcher_loop(self):
        """Real-time whale tracking from onchain data"""
        while self.running:
            try:
                conn = sqlite3.connect(self.onchain_db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Get the latest big trade
                cursor.execute("SELECT * FROM trades_raw ORDER BY timestamp DESC LIMIT 1")
                row = cursor.fetchone()
                conn.close()

                if row and row['timestamp'] != self.last_posted_whale_trade:
                    self.last_posted_whale_trade = row['timestamp']
                    addr_short = f"{row['address'][:6]}...{row['address'][-4:]}"
                    
                    content = (
                        f"🐳 巨鲸出没警告！

"
                        f"地址 `{addr_short}` 刚刚在 Polymarket 投入了 **${row['amount']:,.0f} USDC**！
"
                        f"📍 标的 ID: {row['condition_id'][:10]}...

"
                        "聪明钱正在入场，你跟吗？👀
"
                        "#SmartMoney #Polymarket #WhaleAlert #IrisQuant"
                    )
                    
                    self._publish(content)
            except Exception as e:
                pass # Silently handle DB locked or table missing during init
            await asyncio.sleep(60) # Check every minute

    async def _market_analysis_loop(self):
        """Post at 09:00, 14:00, 20:00"""
        times = [9, 14, 20]
        while self.running:
            now = datetime.now()
            next_hour_list = [t for t in times if t > now.hour]
            next_hour = min(next_hour_list) if next_hour_list else times[0]
            
            target = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            if not next_hour_list:
                target += timedelta(days=1)
                
            await asyncio.sleep(max(0, (target - now).total_seconds()))
            await self._post_market_opinion()

    async def _post_market_opinion(self):
        # Mocking intelligence from news/onchain
        opinions = [
            "🔍 结合当前链上持仓分布，BTC 在 68k 附近的支撑依然强劲。#BTC #MarketAnalysis",
            "📊 链上数据显示散户正在割肉，而 Smart Money 正在悄悄建仓。机会就在恐慌中。#IrisQuant",
            "🌐 宏观新闻偏向中性，但 Polymarket 预测胜率出现了显著偏离，套利空间已现。#Polymarket"
        ]
        content = random.choice(opinions) + "

你怎么看？评论区告诉我 👇"
        self._publish(content)

    async def _engagement_loop(self):
        """Weekly interaction (approx every 2.3 days)"""
        while self.running:
            await asyncio.sleep(3600 * 24 * 2.3)
            topics = [
                "🗳️ 投票：你认为下周 BTC 会突破 $75,000 吗？
1️⃣ 会的，起飞 🚀
2️⃣ 不会，震荡 🦀",
                "❓ 提问时间：关于 AI 自动交易系统，你最关心的指标是什么？胜率还是回撤？",
                "🔥 猜猜看：IrisQuant 下一个接入的协议会是什么？猜对有惊喜（并没有）。"
            ]
            content = random.choice(topics) + "

#IrisQuant #Community #Crypto"
            self._publish(content)

    def _publish(self, content):
        # In actual implementation, this would call Twitter/Telegram API
        # For now, we log it with a distinct format for extraction
        logger.info(f"
[POST_TO_SOCIAL]
{content}
[/POST_TO_SOCIAL]")

async def main():
    agent = SocialAgent()
    await agent.start()
    try:
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
