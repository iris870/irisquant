import aiohttp
import asyncio
import subprocess
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from simulation.exchange_sim import sim_exchange

app = FastAPI(title="IrisQuant Dashboard")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

class PM2Manager:
    @staticmethod
    async def get_all_statuses():
        try:
            # Run pm2 jlist to get JSON output of all processes
            process = await asyncio.create_subprocess_exec(
                "pm2", "jlist",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            if stdout:
                data = json.loads(stdout.decode())
                statuses = []
                for proc in data:
                    statuses.append({
                        "name": proc["name"],
                        "status": proc["pm2_env"]["status"],
                        "restarts": proc["pm2_env"]["restart_time"],
                        "memory": f"{proc['monit']['memory'] / (1024 * 1024):.1f}MB",
                        "cpu": f"{proc['monit']['cpu']}%"
                    })
                return statuses
        except Exception as e:
            print(f"Error fetching PM2 status: {e}")
        return []

class BinanceClient:
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
    
    async def get_ticker(self, symbol="BTCUSDT"):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/ticker/24hr?symbol={symbol}", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "symbol": symbol,
                            "price": data["lastPrice"],
                            "change": data["priceChangePercent"],
                            "high": data["highPrice"],
                            "low": data["lowPrice"],
                            "status": "online"
                        }
            except Exception:
                pass
            return {"status": "offline", "price": "0", "change": "0"}

class NewsClient:
    def __init__(self):
        self.cc_url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
    
    async def get_latest(self, limit=5):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.cc_url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_news = data.get("Data", [])
                        news_list = []
                        for item in raw_news:
                            news_list.append({
                                "title": item.get("title"),
                                "url": item.get("url"),
                                "source": item.get("source"),
                                "sentiment": self._analyze_sentiment(item.get("title", ""))
                            })
                        # Return all news found
                        return {"news": news_list, "status": "online"}
            except Exception:
                pass
            return {"news": [], "status": "offline"}

    def _analyze_sentiment(self, text: str) -> str:
        text = text.lower()
        pos_words = ['up', 'surge', 'bull', 'gain', 'buy', 'positive', 'growth', 'rally', 'breakout', 'pump', 'ath']
        neg_words = ['down', 'drop', 'bear', 'loss', 'sell', 'negative', 'fall', 'crash', 'dump', 'sec', 'ban']
        score = 0
        for word in pos_words:
            if word in text: score += 1
        for word in neg_words:
            if word in text: score -= 1
        if score > 0: return "positive"
        if score < 0: return "negative"
        return "neutral"

binance = BinanceClient()
news_client = NewsClient()

class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/accounts")
async def get_accounts():
    # Fetch real-time account status from sim_exchange (shared with LeaderAgent)
    accounts = {}
    for acc_id in ["A", "B", "C"]:
        status = await sim_exchange.fetch_balance(acc_id)
        # Determine risk level based on daily_pnl (matching LeaderAgent logic)
        daily_pnl = status["daily_pnl"]
        if abs(daily_pnl) > 500:
            risk = "high"
        elif abs(daily_pnl) > 200:
            risk = "medium"
        else:
            risk = "low"
        
        accounts[acc_id] = {
            "balance": status["total"],
            "daily_pnl": daily_pnl,
            "risk": risk
        }
    return accounts

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/market")
async def get_market():
    return await binance.get_ticker()

@app.get("/api/news")
async def get_news():
    return await news_client.get_latest()

@app.get("/api/status")
async def get_status():
    market = await binance.get_ticker()
    news = await news_client.get_latest()
    return {
        "binance": market["status"],
        "news_api": news["status"],
        "sim_exchange": "online" # Internal
    }

@app.get("/api/agents/status")
async def get_agents_status():
    return await PM2Manager.get_all_statuses()

@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
