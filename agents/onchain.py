import asyncio
import json
import os
import time
import sqlite3
from typing import List, Dict
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_abi import decode
from dotenv import load_dotenv

# Force load .env from the root directory before anything else
load_dotenv(dotenv_path="/root/irisquant/.env", override=True)

from agents.base import BaseAgent
from core.logger import setup_logger

logger = setup_logger("onchain-agent")

# Polymarket USDC CTF Contract
POLYMARKET_CONTRACT = os.getenv("POLYMARKET_CONTRACT", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
DB_PATH = "/root/irisquant/storage/knowledge.db"

# Minimal ABI for Trade event (PositionModified)
# event PositionModified(indexed bytes32 conditionId, indexed address bettor, uint256[] outcomeIndex, int256 amount, uint256 fee)
ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "conditionId", "type": "bytes32"},
            {"indexed": True, "name": "bettor", "type": "address"},
            {"indexed": False, "name": "outcomeIndex", "type": "uint256[]"},
            {"indexed": False, "name": "amount", "type": "int256"},
            {"indexed": False, "name": "fee", "type": "uint256"}
        ],
        "name": "PositionModified",
        "type": "event"
    }
]

class OnchainAgent(BaseAgent):
    def __init__(self):
        super().__init__("onchain")
        logger.info(f"Connecting to RPC: {RPC_URL}")
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.contract = self.w3.eth.contract(address=self.w3.to_checksum_address(POLYMARKET_CONTRACT), abi=ABI)
        self.threshold = int(os.getenv("SMART_MONEY_THRESHOLD", 5000)) * 10**6 # USDC has 6 decimals
        self._init_db()

    def _init_db(self):
        """Ensure tables exist before use"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS trades_raw (address TEXT, condition_id TEXT, amount REAL, timestamp INTEGER)")
            cur.execute("CREATE TABLE IF NOT EXISTS smart_money (address TEXT PRIMARY KEY, trades INTEGER, win_rate REAL)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB Init Error: {e}")
        
    async def _on_start(self):
        logger.info(f"Onchain agent starting. Monitoring {POLYMARKET_CONTRACT} on Polygon.")
        self.tasks = [
            asyncio.create_task(self._poll_blocks()),
            asyncio.create_task(self._update_smart_money_stats())
        ]

    async def _poll_blocks(self):
        """Poll for new blocks and filter large trades"""
        last_block = self.w3.eth.block_number - 100 # Start 100 blocks back to avoid gaps
        BLOCK_STEP = 2000 # Max blocks per query to avoid RPC limits

        while self.running:
            try:
                # 1. Update w3 reference if needed (handle session timeouts)
                # 2. Get current block
                current_block = self.w3.eth.block_number
                
                # Check if we are too far behind
                target_block = min(last_block + BLOCK_STEP, current_block)

                if target_block > last_block:
                    logger.info(f"Scanning blocks {last_block + 1} to {target_block} (current: {current_block})")
                    
                    try:
                        logs = self.w3.eth.get_logs({
                            "fromBlock": last_block + 1,
                            "toBlock": target_block,
                            "address": self.w3.to_checksum_address(POLYMARKET_CONTRACT)
                        })
                        
                        for log in logs:
                            try:
                                event = self.contract.events.PositionModified().process_log(log)
                                args = event['args']
                                amount_usdc = abs(args['amount']) / 10**6
                                
                                if amount_usdc >= (self.threshold / 10**6):
                                    logger.info(f"Whale detected! {args['bettor']} traded {amount_usdc} USDC on {args['conditionId'].hex()}")
                                    self._record_trade(args['bettor'], args['conditionId'].hex(), amount_usdc)
                            except Exception as e:
                                continue
                        
                        last_block = target_block
                    except Exception as e:
                        if "limit" in str(e).lower() or "400" in str(e) or "invalid block range" in str(e).lower():
                            logger.warning(f"RPC Limit/Range error, reducing step size: {e}")
                            BLOCK_STEP = max(5, BLOCK_STEP // 2)
                        else:
                            raise e
                
                # If caught up, wait. If behind, move to next batch immediately.
                if last_block >= current_block:
                    await asyncio.sleep(10)
                else:
                    await asyncio.sleep(0.1) # Faster fast-forward

            except Exception as e:
                logger.error(f"Critical error in polling loop: {e}")
                await asyncio.sleep(5)

    def _record_trade(self, address, condition_id, amount):
        """Record trade to SQLite and data_recorder for RL analysis"""
        try:
            # 1. Local SQLite record
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT INTO trades_raw VALUES (?, ?, ?, ?)", (address, condition_id, amount, int(time.time())))
            conn.commit()
            conn.close()

            # 2. RL Data Recorder (for cross-agent visibility)
            from core.data_recorder import get_recorder
            from datetime import datetime
            recorder = get_recorder()
            
            trade_data = {
                "timestamp": int(datetime.now().timestamp()),
                "strategy": "onchain_whale_detection",
                "direction": "whale_activity",
                "entry_price": 0.0,
                "exit_price": 0.0,
                "position_size": amount,
                "pnl": 0.0,
                "market_state": {
                    "bettor": address,
                    "condition_id": condition_id,
                    "source": "polymarket_contract"
                }
            }
            recorder.record_trade(trade_data)
            logger.info(f"Recorded whale trade for RL: {amount} USDC")
        except Exception as e:
            logger.error(f"Error recording trade: {e}")

    async def _update_smart_money_stats(self):
        """Hourly update of smart_money table"""
        while self.running:
            try:
                logger.info("Updating smart money stats...")
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                
                # Logic: count trades and estimate win rate (simplified for demo)
                # In production, we'd need to track outcome resolution.
                cur.execute("""
                    INSERT INTO smart_money (address, trades, win_rate)
                    SELECT address, COUNT(*), 0.75 -- Mock win_rate for now
                    FROM trades_raw
                    GROUP BY address
                    HAVING COUNT(*) >= 5
                    ON CONFLICT(address) DO UPDATE SET
                    trades = excluded.trades,
                    win_rate = 0.80 -- Dynamic update would go here
                """)
                
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error updating smart money: {e}")
            await asyncio.sleep(3600)

async def run_agent():
    agent = OnchainAgent()
    await agent.start()
    try:
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(run_agent())
