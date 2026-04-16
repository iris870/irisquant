/**
 * 聪明钱监控器 v2
 * 只负责监控 qualified-wallets.json 中的钱包交易
 */
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';

interface QualifiedWallet {
  address: string;
  winRate: number;
  numTrades: number;
  totalPnl: number;
}

interface Trade {
  id: string;
  trader: string;
  marketId: string;
  outcome: string;
  amount: number;
  price: number;
  timestamp: number;
  transactionHash: string;
}

class SmartMoneyMonitorV2 {
  private qualifiedWallets: QualifiedWallet[] = [];
  private lastCheckTime: number = Date.now() / 1000;
  private checkInterval: number = 60000; // 60秒
  private tradesHistory: Trade[] = [];
  
  constructor() {
    this.loadQualifiedWallets();
  }
  
  async start(): Promise<void> {
    console.log('\n' + '='.repeat(60));
    console.log('📡 聪明钱实时监控启动 v2');
    console.log(`⏰ 启动时间: ${new Date().toLocaleString()}`);
    console.log(`🔄 检查间隔: ${this.checkInterval / 1000} 秒`);
    console.log(`👛 监控钱包: ${this.qualifiedWallets.length} 个`);
    console.log('='.repeat(60) + '\n');
    
    await this.checkNewTrades();
    
    setInterval(async () => {
      await this.checkNewTrades();
    }, this.checkInterval);
  }
  
  private loadQualifiedWallets(): void {
    const filePath = '/root/projects/irisSMART/config/qualified-wallets.json';
    if (fs.existsSync(filePath)) {
      try {
        const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        this.qualifiedWallets = data.wallets || [];
        console.log(`📋 加载了 ${this.qualifiedWallets.length} 个聪明钱钱包`);
      } catch (e) {
        console.error('加载钱包失败:', e);
      }
    } else {
      console.log('📋 无聪明钱钱包配置，请先运行 scanner');
    }
  }
  
  private async checkNewTrades(): Promise<void> {
    if (this.qualifiedWallets.length === 0) return;
    
    const walletAddresses = this.qualifiedWallets.map(w => w.address.toLowerCase());
    const since = this.lastCheckTime;
    this.lastCheckTime = Date.now() / 1000;
    
    try {
      // 使用官方 Data API（不限流）
      const url = `https://data-api.polymarket.com/trades?limit=100&timestamp_gt=${since}`;
      const response = await axios.get(url);
      const allTrades = response.data || [];
      
      // 过滤出监控钱包的交易
      const newTrades = allTrades.filter((trade: any) => 
        walletAddresses.includes(trade.proxyWallet?.toLowerCase())
      );
      
      if (newTrades.length > 0) {
        this.processNewTrades(newTrades);
      }
    } catch (error) {
      console.error('获取交易失败:', error);
    }
  }
  
  private processNewTrades(trades: any[]): void {
    console.log(`\n📊 发现 ${trades.length} 笔新交易`);
    
    for (const trade of trades) {
      const wallet = this.qualifiedWallets.find(
        w => w.address.toLowerCase() === trade.proxyWallet?.toLowerCase()
      );
      
      console.log('\n🚨 ' + '='.repeat(40));
      console.log(`🔥 聪明钱交易警报！`);
      console.log(`👛 钱包: ${trade.proxyWallet?.slice(0, 10)}...`);
      if (wallet) {
        console.log(`📈 胜率: ${wallet.winRate.toFixed(1)}%`);
        console.log(`📊 总交易: ${wallet.numTrades} 笔`);
        console.log(`💰 总盈亏: $${wallet.totalPnl.toLocaleString()}`);
      }
      console.log(`🎲 方向: ${trade.outcome === 'Yes' ? 'YES' : 'NO'}`);
      console.log(`💰 金额: $${trade.size?.toLocaleString() || 0}`);
      console.log(`💵 价格: $${trade.price?.toFixed(4) || 0}`);
      console.log(`⏰ 时间: ${new Date(trade.timestamp * 1000).toLocaleString()}`);
      console.log('='.repeat(50) + '\n');
    }
  }
}

if (require.main === module) {
  const monitor = new SmartMoneyMonitorV2();
  monitor.start().catch(console.error);
}

export { SmartMoneyMonitorV2 };
