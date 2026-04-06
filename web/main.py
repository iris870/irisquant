import asyncio
import httpx
import json
import subprocess
import os
import time
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# 🌟 严谨获取模板目录绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_real_price(symbol):
    """从币安抓取实盘价格"""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=2.0)
            data = res.json()
            return float(data['price'])
    except:
        return None

def get_sim_data():
    """读取仿真状态文件"""
    try:
        with open("/tmp/irisquant_sim_state.json", "r") as f:
            data = json.load(f)
            return data.get("accounts", {}), data.get("markets", {})
    except:
        return {}, {}

def get_pm2_agents():
    """获取 PM2 进程状态"""
    try:
        result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
        data = json.loads(result.stdout)
        agents = []
        online = 0
        for p in data:
            name = p.get('name', 'unknown')
            status = p.get('pm2_env', {}).get('status', 'unknown')
            cpu = p.get('monit', {}).get('cpu', 0)
            mem = p.get('monit', {}).get('memory', 0)
            if status == 'online': online += 1
            agents.append({
                "name": name,
                "status": status,
                "cpu": f"{cpu}%",
                "memory": f"{mem/1024/1024:.1f}MB",
                "restarts": p.get('pm2_env', {}).get('restart_time', 0)
            })
        
        # 获取数据库大小
        db_size = "0M"
        try:
            db_res = subprocess.run(["du", "-sh", "/root/irisquant/data/knowledge.db"], capture_output=True, text=True)
            db_size = db_res.stdout.split()[0]
        except: pass
            
        return online, len(data), agents, db_size
    except:
        return 0, 0, [], "0M"

# --- API 路由 ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/accounts")
async def accounts():
    sim_accounts, _ = get_sim_data()
    NAME_MAP = {
        "A": "BINANCE_MAIN",
        "B": "OKX_SUB1",
        "C": "POLYMARKET",
        "W": "WEATHER_ALPHA"
    }
    result = {}
    for aid, acc_data in sim_accounts.items():
        internal_id = NAME_MAP.get(aid, f"ACCOUNT_{aid}")
        balance = acc_data.get("balance", 0.0)
        pnl = acc_data.get("daily_pnl", 0.0)
        result[internal_id] = {
            "balance": balance,
            "daily_pnl": pnl,
            "pnl_pcnt": (pnl / balance * 100) if balance > 0 else 0,
            "risk": "low"
        }
    return result

@app.get("/api/status")
async def status():
    # 状态标记
    binance_ok = False
    news_ok = False
    sim_ok = False
    uptime_str = "---"
    rl_db_size = "0M"
    online, total, agents, db_size = 0, 0, [], "0M"

    try:
        # 1. 探测 Binance
        async with httpx.AsyncClient() as client:
            res = await client.get("https://api.binance.com/api/v3/ping", timeout=2.0)
            if res.status_code == 200: binance_ok = True
    except: pass

    try:
        # 2. 获取 PM2 列表一次，共用
        pm2_res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
        pm2_data = json.loads(pm2_res.stdout)
        
        online = 0
        total = len(pm2_data)
        agents = [] # 🌟 确保重置列表
        for p in pm2_data:
            name = p.get('name', 'unknown')
            st = p.get('pm2_env', {}).get('status', 'unknown')
            cpu = p.get('monit', {}).get('cpu', 0)
            mem = p.get('monit', {}).get('memory', 0)
            restarts = p.get('pm2_env', {}).get('restart_time', 0)
            
            # 添加到详情列表
            agents.append({
                "name": name,
                "status": st,
                "cpu": f"{cpu}%",
                "memory": f"{mem/1024/1024:.1f}MB",
                "restarts": restarts
            })
            
            # 标记 News
            if name == 'news' and st == 'online':
                news_ok = True
            
            # 计算 Uptime (以 web 进程为基准)
            if name == 'web':
                start_ms = p.get('pm2_env', {}).get('pm_uptime', 0)
                if start_ms > 0:
                    start_dt = datetime.fromtimestamp(start_ms / 1000)
                    delta_s = int((time.time() * 1000 - start_ms) / 1000)
                    h = delta_s // 3600
                    m = (delta_s % 3600) // 60
                    uptime_str = f"{h}h {m}m ({start_dt.strftime('%m-%d %H:%M')})"
            
            # 统计 online 数量
            if st == 'online':
                online += 1
    except: pass

    try:
        # 3. Sim 状态
        state_path = "/tmp/irisquant_sim_state.json"
        if os.path.exists(state_path) and (time.time() - os.path.getmtime(state_path) < 60):
            sim_ok = True
    except: pass

    try:
        # 4. DB 大小
        db_res = subprocess.run(["du", "-sh", "/root/irisquant/data/knowledge.db"], capture_output=True, text=True)
        db_size = db_res.stdout.split()[0]
        
        rl_res = subprocess.run(["du", "-sh", "/root/irisquant/data/rl_data.db"], capture_output=True, text=True)
        rl_db_size = rl_res.stdout.split()[0]
    except: pass
    
    return {
        "binance_market": "🟢" if binance_ok else "🔴",
        "news_source": "🟢" if news_ok else "🔴",
        "sim_exchange": "🟢" if sim_ok else "🔴",
        "uptime": uptime_str,
        "rl_db_size": rl_db_size,
        "agents_online": online,
        "agents_total": total,
        "agents": agents,
        "db_size": db_size
    }

@app.get("/api/markets")
async def markets():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    tasks = [fetch_real_price(s) for s in symbols]
    prices = await asyncio.gather(*tasks)
    
    return {
        "BTC": {"price": prices[0] or 69000.0, "change": 1.25},
        "ETH": {"price": prices[1] or 3500.0, "change": -0.45},
        "BNB": {"price": prices[2] or 605.0, "change": 0.82},
        "SOL": {"price": prices[3] or 145.0, "change": 3.12}
    }

@app.get("/api/logs")
async def get_logs(limit: int = 50, keyword: str = None):
    """获取历史日志快照，支持关键词过滤"""
    try:
        # 使用 pm2 logs --lines 获取最后 N 行
        # 注意：pm2 logs --raw 并不直接支持 grep，我们需要在 Python 层过滤
        result = subprocess.run(
            ["pm2", "logs", "--raw", "--lines", str(limit * 2), "--nostream"],
            capture_output=True, text=True, timeout=3.0
        )
        lines = result.stdout.splitlines()
        parsed = []
        
        search_kw = keyword.lower() if keyword else None
        
        for l in lines:
            tag = "SYSTEM"
            msg = l
            if "|" in l:
                parts = l.split("|", 1)
                tag = parts[0].strip()
                msg = parts[1].strip()
            
            # 关键词过滤逻辑
            if search_kw:
                if search_kw not in tag.lower() and search_kw not in msg.lower():
                    # 特殊处理 "错误" -> "error"
                    if search_kw == "错误" and ("error" in msg.lower() or "failed" in msg.lower()):
                        pass
                    else:
                        continue
            
            parsed.append({"agent": tag, "message": msg})
            if len(parsed) >= limit:
                break
                
        return parsed
    except Exception as e:
        print(f"Log API Error: {e}")
        return []

@app.websocket("/ws/logs/all")
async def websocket_logs_all(websocket: WebSocket):
    await websocket.accept()
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            "pm2", "logs", "--raw", "--lines", "50",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        while True:
            line = await process.stdout.readline()
            if not line: break
            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str:
                tag = "SYSTEM"
                if "|" in line_str:
                    tag = line_str.split("|")[0].strip()
                await websocket.send_json({"agent": tag, "message": line_str})
    except WebSocketDisconnect:
        pass
    finally:
        if process:
            try: process.terminate()
            except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
