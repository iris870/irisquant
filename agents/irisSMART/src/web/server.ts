import express from 'express';
import { Server } from 'socket.io';
import { createServer } from 'node:http';
import * as path from 'node:path';
import * as fs from 'node:fs';

const app = express();
const server = createServer(app);
const io = new Server(server);

const PORT = 3000;
const BASE_PATH = '/smart-money';

app.use(BASE_PATH, express.static(path.join(__dirname, '../../public')));// 代理 Polymarket 机器人 API
app.use('/smart-money/api/polymarket', async (req, res) => {
    const target = 'http://127.0.0.1:3002/api/polymarket' + req.url;
    try {
        const fetch = (await import('node-fetch')).default;
        const response = await fetch(target);
        const data = await response.json();
        res.json(data);
    } catch(e) {
        console.error('代理错误:', e);
        res.status(500).json({ error: '机器人服务未启动' });
    }
});

app.get(`${BASE_PATH}/api/wallets`, (req, res) => {
  const filePath = path.join(__dirname, '../../config/qualified-wallets.json');
  if (fs.existsSync(filePath)) {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    res.json(data);
  } else {
    res.json({ wallets: [] });
  }
});

app.get(`${BASE_PATH}/api/trades`, (req, res) => {
  const filePath = path.join(__dirname, '../../config/recent-trades.json');
  if (fs.existsSync(filePath)) {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    res.json(data.slice(0, 50));
  } else {
    res.json([]);
  }
});

app.get(`${BASE_PATH}/api/signals`, (req, res) => {
  const filePath = path.join(__dirname, '../../config/signal-stats.json');
  if (fs.existsSync(filePath)) {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    res.json(data.slice(0, 50));
  } else {
    res.json([]);
  }
});

app.get(`${BASE_PATH}/api/status`, (req, res) => {
  res.json({ status: 'running', lastUpdate: new Date().toISOString(), walletsCount: 15 });
});

io.of(BASE_PATH).on('connection', (socket) => {
  console.log('Web 客户端已连接');
  socket.on('disconnect', () => console.log('Web 客户端断开'));
});

server.listen(PORT, () => {
  console.log(`🌐 irisSMART 已启动: http://localhost:${PORT}${BASE_PATH}`);
});

export { app, io };
