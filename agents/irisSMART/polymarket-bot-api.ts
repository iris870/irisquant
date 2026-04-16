import express from 'express';
import fs from 'fs';
import path from 'path';

const app = express();
const PORT = 3002;

// CORS 中间件
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    if (req.method === 'OPTIONS') {
        res.sendStatus(200);
    } else {
        next();
    }
});

const DATA_DIR = '/root/projects/irisSMART/data';
const TRADES_FILE = path.join(DATA_DIR, 'bot-trades.json');
const BALANCE_FILE = path.join(DATA_DIR, 'bot-balance.json');
const SIGNALS_FILE = path.join(DATA_DIR, 'bot-signals.json');

if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
}

if (!fs.existsSync(TRADES_FILE)) {
    fs.writeFileSync(TRADES_FILE, JSON.stringify([]));
}
if (!fs.existsSync(BALANCE_FILE)) {
    fs.writeFileSync(BALANCE_FILE, JSON.stringify({ usdc: 100, matic: 0.5, lastUpdate: new Date().toISOString() }));
}
if (!fs.existsSync(SIGNALS_FILE)) {
    fs.writeFileSync(SIGNALS_FILE, JSON.stringify([]));
}

async function getMarkets() {
    const url = 'https://gamma-api.polymarket.com/markets?limit=20&closed=false&order=volume24hr_desc';
    const response = await fetch(url);
    const markets = await response.json();
    
    return markets.map((m: any) => {
        let yesPrice = 0.5, noPrice = 0.5;
        if (m.outcomePrices) {
            let prices = m.outcomePrices;
            if (typeof prices === 'string') {
                try { prices = JSON.parse(prices); } catch { }
            }
            if (Array.isArray(prices) && prices.length >= 2) {
                yesPrice = parseFloat(prices[0]) || 0.5;
                noPrice = parseFloat(prices[1]) || 0.5;
            }
        }
        return {
            id: m.id,
            question: m.question,
            yesPrice,
            noPrice,
            volume24h: m.volume24hr || 0,
            endDate: m.endDateIso
        };
    });
}

async function generateSignals() {
    const markets = await getMarkets();
    const signals = [];
    
    for (const market of markets.slice(0, 10)) {
        let action = null;
        let reason = '';
        let confidence = 0;
        
        if (market.yesPrice < 0.05) {
            action = 'BUY_YES';
            reason = `YES 价格仅 ${(market.yesPrice * 100).toFixed(1)}%，高赔率机会`;
            confidence = 0.7;
        } else if (market.yesPrice > 0.95) {
            action = 'BUY_NO';
            reason = `NO 价格仅 ${((1 - market.yesPrice) * 100).toFixed(1)}%，高赔率机会`;
            confidence = 0.7;
        } else if (market.volume24h > 50000 && market.yesPrice < 0.3) {
            action = 'BUY_YES';
            reason = `交易量激增 $${(market.volume24h / 1000).toFixed(0)}k，价格 ${(market.yesPrice * 100).toFixed(1)}% 偏低`;
            confidence = 0.6;
        } else if (market.yesPrice < 0.1) {
            action = 'BUY_YES';
            reason = `YES 价格 ${(market.yesPrice * 100).toFixed(1)}%，低于阈值`;
            confidence = 0.65;
        } else if (market.yesPrice > 0.9) {
            action = 'BUY_NO';
            reason = `YES 价格 ${(market.yesPrice * 100).toFixed(1)}%，高于阈值`;
            confidence = 0.65;
        }
        
        if (action) {
            signals.push({
                id: `${Date.now()}-${market.id}`,
                marketId: market.id,
                marketQuestion: market.question,
                action,
                price: action === 'BUY_YES' ? market.yesPrice : market.noPrice,
                reason,
                confidence,
                detectedAt: new Date().toISOString(),
                status: 'pending'
            });
        }
    }
    
    return signals;
}

async function saveNewSignals() {
    const existingSignals = JSON.parse(fs.readFileSync(SIGNALS_FILE, 'utf-8'));
    const newSignals = await generateSignals();
    
    const existingIds = new Set(existingSignals.map((s: any) => s.marketId));
    const uniqueNewSignals = newSignals.filter(s => !existingIds.has(s.marketId));
    
    if (uniqueNewSignals.length > 0) {
        const updatedSignals = [...uniqueNewSignals, ...existingSignals].slice(0, 100);
        fs.writeFileSync(SIGNALS_FILE, JSON.stringify(updatedSignals, null, 2));
    }
    
    return uniqueNewSignals;
}

async function executeSignals() {
    const signals = JSON.parse(fs.readFileSync(SIGNALS_FILE, 'utf-8'));
    const pendingSignals = signals.filter((s: any) => s.status === 'pending');
    const trades = JSON.parse(fs.readFileSync(TRADES_FILE, 'utf-8'));
    const balance = JSON.parse(fs.readFileSync(BALANCE_FILE, 'utf-8'));
    
    for (const signal of pendingSignals.slice(0, 5)) {
        const amount = 10;
        const cost = signal.price * amount;
        
        if (cost <= balance.usdc) {
            const trade = {
                id: `trade-${Date.now()}-${signal.id}`,
                signalId: signal.id,
                marketId: signal.marketId,
                marketQuestion: signal.marketQuestion,
                action: signal.action,
                amount,
                price: signal.price,
                cost,
                timestamp: new Date().toISOString(),
                status: 'executed'
            };
            
            trades.unshift(trade);
            balance.usdc -= cost;
            signal.status = 'executed';
            
            console.log(`✅ 执行交易: ${signal.action} ${signal.marketQuestion.substring(0, 40)}... $${cost.toFixed(2)}`);
        } else {
            signal.status = 'failed_insufficient_balance';
            console.log(`❌ 余额不足: 需要 $${cost.toFixed(2)}, 剩余 $${balance.usdc}`);
        }
    }
    
    fs.writeFileSync(TRADES_FILE, JSON.stringify(trades.slice(0, 100), null, 2));
    fs.writeFileSync(BALANCE_FILE, JSON.stringify({ ...balance, lastUpdate: new Date().toISOString() }, null, 2));
    fs.writeFileSync(SIGNALS_FILE, JSON.stringify(signals, null, 2));
}

app.get('/api/polymarket/status', (req, res) => {
    res.json({ success: true, data: { running: true, version: '1.0.0', strategies: ['极端值', '交易量激增', '阈值'], lastScan: new Date().toISOString() } });
});

app.get('/api/polymarket/balance', (req, res) => {
    const balance = JSON.parse(fs.readFileSync(BALANCE_FILE, 'utf-8'));
    res.json({ success: true, data: balance });
});

app.get('/api/polymarket/trades', (req, res) => {
    const trades = JSON.parse(fs.readFileSync(TRADES_FILE, 'utf-8'));
    res.json({ success: true, data: trades });
});

app.get('/api/polymarket/signals', (req, res) => {
    const signals = JSON.parse(fs.readFileSync(SIGNALS_FILE, 'utf-8'));
    res.json({ success: true, data: signals });
});

app.get('/api/polymarket/markets', async (req, res) => {
    const markets = await getMarkets();
    res.json({ success: true, data: markets.slice(0, 10) });
});

app.post('/api/polymarket/scan', async (req, res) => {
    const newSignals = await saveNewSignals();
    await executeSignals();
    res.json({ success: true, newSignals: newSignals.length });
});

setInterval(async () => {
    console.log('🔍 扫描新信号...');
    await saveNewSignals();
    await executeSignals();
}, 5 * 60 * 1000);

setTimeout(async () => {
    console.log('🚀 启动首次扫描...');
    await saveNewSignals();
    await executeSignals();
}, 3000);

app.listen(PORT, '0.0.0.0', () => {
    console.log(`🤖 Polymarket 机器人 API 已启动: http://0.0.0.0:${PORT}`);
});
