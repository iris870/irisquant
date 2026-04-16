/**
 * 聪明钱扫描器 v4
 * 改进的胜率计算算法
 */
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';

interface Trade {
  proxyWallet: string;
  side: string;
  size: number;
  price: number;
  timestamp: number;
  conditionId: string;
  outcome: string;
}

interface WalletTrade {
  buyPrice: number;
  sellPrice: number;
  size: number;
  outcome: string;
  isClosed: boolean;
  pnl: number;
}

interface WalletStats {
  address: string;
  totalTrades: number;
  completedTrades: number;
  winningTrades: number;
  losingTrades: number;
  totalVolume: number;
  totalPnl: number;
  winRate: number;
  avgWinSize: number;
  avgLossSize: number;
  profitFactor: number;
}

interface QualifiedWallet {
  address: string;
  winRate: number;
  numTrades: number;
  totalPnl: number;
  totalVolume: number;
  profitFactor: number;
  qualifiedAt: string;
}

class SmartMoneyScannerV4 {
  private outputPath = path.join(__dirname, '../../../config/qualified-wallets.json');
  private minTrades = 10;           // 最少交易 10 笔
  private minWinRate = 50;          // 最低胜率 55%
  private minProfitFactor = 1.0;    // 最低盈亏比 1.2
  private maxWallets = 20;
  private daysToAnalyze = 30;

  async scan(): Promise<void> {
    console.log('\n🔍 开始扫描聪明钱 v4（改进胜率计算）...\n');
    
    // 获取所有交易
    const allTrades = await this.getAllTrades();
    console.log(`📊 获取到 ${allTrades.length} 条交易记录`);
    
    if (allTrades.length === 0) {
      console.log('⚠️ 未获取到交易数据');
      return;
    }
    
    // 按钱包分组统计
    const walletStats = await this.calculateWalletStats(allTrades);
    const walletCount = Object.keys(walletStats).length;
    console.log(`📊 发现 ${walletCount} 个活跃钱包`);
    
    // 筛选聪明钱
    const qualified = this.filterQualifiedWallets(walletStats);
    console.log(`📊 筛选出 ${qualified.length} 个合格钱包`);
    
    // 保存结果
    this.saveQualifiedWallets(qualified);
    
    // 打印排行榜
    if (qualified.length > 0) {
      console.log('\n🏆 聪明钱排行榜 (按胜率排序):');
      qualified.slice(0, 10).forEach((w, i) => {
        console.log(`${i+1}. ${w.address.slice(0, 10)}... | 胜率: ${w.winRate.toFixed(1)}% | 交易: ${w.numTrades} | 盈亏比: ${w.profitFactor.toFixed(2)} | 盈亏: $${w.totalPnl.toFixed(2)}`);
      });
    } else {
      console.log('\n⚠️ 未发现符合条件的聪明钱钱包');
    }
    
    console.log(`\n✅ 扫描完成\n`);
  }

  private async getAllTrades(): Promise<any[]> {
    const allTrades: any[] = [];
    const since = Math.floor(Date.now() / 1000) - this.daysToAnalyze * 24 * 3600;
    let cursor: string | undefined = undefined;
    
    try {
      while (allTrades.length < 10000) {
        let url = `https://data-api.polymarket.com/trades?limit=500&timestamp_gt=${since}`;
        if (cursor) url += `&cursor=${cursor}`;
        
        const response = await axios.get(url);
        const trades = response.data || [];
        if (trades.length === 0) break;
        
        for (const trade of trades) {
          if (trade.proxyWallet && trade.size && trade.price) {
            allTrades.push(trade);
          }
        }
        
        const nextCursor = response.headers?.['next-cursor'];
        if (nextCursor) cursor = nextCursor;
        else break;
        
        await this.sleep(100);
      }
    } catch (error) {
      console.error('获取交易失败:', error);
    }
    
    return allTrades;
  }

  private async calculateWalletStats(trades: any[]): Promise<{ [key: string]: WalletStats }> {
    const statsMap: { [key: string]: WalletStats } = {};
    const walletTrades: { [key: string]: WalletTrade[] } = {};
    
    // 按市场分组，用于匹配买卖对
    const marketTrades: { [key: string]: any[] } = {};
    
    for (const trade of trades) {
      const address = trade.proxyWallet;
      const marketId = trade.conditionId;
      const key = `${address}|${marketId}`;
      
      if (!marketTrades[key]) {
        marketTrades[key] = [];
      }
      marketTrades[key].push(trade);
    }
    
    // 计算每个钱包的盈亏
    for (const [key, marketTradeList] of Object.entries(marketTrades)) {
      const [address, marketId] = key.split('|');
      
      if (!statsMap[address]) {
        statsMap[address] = {
          address: address,
          totalTrades: 0,
          completedTrades: 0,
          winningTrades: 0,
          losingTrades: 0,
          totalVolume: 0,
          totalPnl: 0,
          winRate: 0,
          avgWinSize: 0,
          avgLossSize: 0,
          profitFactor: 0
        };
      }
      
      // 按时间排序
      marketTradeList.sort((a, b) => a.timestamp - b.timestamp);
      
      let buyTrades: any[] = [];
      let sellTrades: any[] = [];
      
      for (const trade of marketTradeList) {
        if (trade.side === 'BUY') {
          buyTrades.push(trade);
        } else {
          sellTrades.push(trade);
        }
        statsMap[address].totalVolume += (trade.size * trade.price);
        statsMap[address].totalTrades++;
      }
      
      // 匹配买卖对计算盈亏（FIFO）
      let buyIndex = 0;
      for (const sell of sellTrades) {
        if (buyIndex >= buyTrades.length) break;
        
        const buy = buyTrades[buyIndex];
        const buyValue = buy.size * buy.price;
        const sellValue = sell.size * sell.price;
        const pnl = sellValue - buyValue;
        
        statsMap[address].completedTrades++;
        statsMap[address].totalPnl += pnl;
        
        if (pnl > 0) {
          statsMap[address].winningTrades++;
          statsMap[address].avgWinSize += pnl;
        } else {
          statsMap[address].losingTrades++;
          statsMap[address].avgLossSize += Math.abs(pnl);
        }
        
        buyIndex++;
      }
    }
    
    // 计算最终指标
    for (const address in statsMap) {
      const stats = statsMap[address];
      
      if (stats.completedTrades > 0) {
        stats.winRate = (stats.winningTrades / stats.completedTrades) * 100;
        stats.avgWinSize = stats.avgWinSize / stats.winningTrades;
        stats.avgLossSize = stats.avgLossSize / stats.losingTrades;
        stats.profitFactor = stats.avgWinSize / (stats.avgLossSize || 1);
      }
    }
    
    return statsMap;
  }

  private filterQualifiedWallets(statsMap: { [key: string]: WalletStats }): QualifiedWallet[] {
    const qualified: QualifiedWallet[] = [];
    
    for (const address in statsMap) {
      const stats = statsMap[address];
      
      if (stats.completedTrades >= this.minTrades && 
          stats.winRate >= this.minWinRate &&
          stats.profitFactor >= this.minProfitFactor) {
        qualified.push({
          address: address,
          winRate: stats.winRate,
          numTrades: stats.completedTrades,
          totalPnl: stats.totalPnl,
          totalVolume: stats.totalVolume,
          profitFactor: stats.profitFactor,
          qualifiedAt: new Date().toISOString()
        });
      }
    }
    
    // 按综合得分排序（胜率 * 盈亏比）
    qualified.sort((a, b) => {
      const scoreA = a.winRate * a.profitFactor;
      const scoreB = b.winRate * b.profitFactor;
      return scoreB - scoreA;
    });
    
    return qualified.slice(0, this.maxWallets);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private saveQualifiedWallets(wallets: QualifiedWallet[]): void {
    const dir = path.dirname(this.outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    fs.writeFileSync(this.outputPath, JSON.stringify({
      lastUpdated: new Date().toISOString(),
      count: wallets.length,
      wallets: wallets
    }, null, 2));
    
    console.log(`💾 已保存到: ${this.outputPath}`);
  }
}

if (require.main === module) {
  const scanner = new SmartMoneyScannerV4();
  scanner.scan().catch(console.error);
}

export { SmartMoneyScannerV4 };
