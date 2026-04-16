/**
 * 聪明钱扫描器 v3
 * 完全使用官方 Data API，不依赖 Graph 子图
 */
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';

interface WalletStats {
  address: string;
  totalTrades: number;
  totalVolume: number;
  totalBuyVolume: number;
  totalSellVolume: number;
  uniqueMarkets: Set<string>;
}

interface QualifiedWallet {
  address: string;
  winRate: number;
  numTrades: number;
  totalPnl: number;
  totalVolume: number;
  qualifiedAt: string;
}

class SmartMoneyScannerV3 {
  private outputPath = path.join(__dirname, '../../../config/qualified-wallets.json');
  private minTrades = 10;           // 最少交易 30 笔
  private maxWallets = 20;          // 最多保存 20 个钱包
  private daysToAnalyze = 30;       // 分析最近30天的数据

  async scan(): Promise<void> {
    console.log('\n🔍 开始扫描聪明钱（纯官方 API）...\n');
    
    // 步骤1: 获取近期所有交易
    const allTrades = await this.getAllTrades();
    console.log(`📊 获取到 ${allTrades.length} 条交易记录`);
    
    if (allTrades.length === 0) {
      console.log('⚠️ 未获取到交易数据');
      return;
    }
    
    // 步骤2: 按钱包聚合统计
    const walletStats = this.aggregateWalletStats(allTrades);
    const walletCount = Object.keys(walletStats).length;
    console.log(`📊 发现 ${walletCount} 个活跃钱包`);
    
    // 步骤3: 筛选活跃钱包
    const qualified = this.filterQualifiedWallets(walletStats);
    console.log(`📊 筛选出 ${qualified.length} 个合格钱包`);
    
    // 步骤4: 保存结果
    this.saveQualifiedWallets(qualified);
    
    // 打印前10个
    if (qualified.length > 0) {
      console.log('\n🏆 活跃钱包排行榜 (Top 10):');
      qualified.slice(0, 10).forEach((w, i) => {
        console.log(`${i+1}. ${w.address.slice(0, 10)}... | 交易: ${w.numTrades} | 交易量: $${w.totalVolume.toFixed(0)}`);
      });
    } else {
      console.log('\n⚠️ 未发现符合条件的活跃钱包');
      console.log('提示: 可以降低 minTrades 阈值重新扫描');
    }
    
    console.log(`\n✅ 扫描完成，已保存 ${qualified.length} 个活跃钱包\n`);
  }
  
  private async getAllTrades(): Promise<any[]> {
    const allTrades: any[] = [];
    const since = Math.floor(Date.now() / 1000) - this.daysToAnalyze * 24 * 3600;
    let cursor: string | undefined = undefined;
    
    try {
      while (allTrades.length < 5000) {
        let url = `https://data-api.polymarket.com/trades?limit=500&timestamp_gt=${since}`;
        if (cursor) {
          url += `&cursor=${cursor}`;
        }
        
        const response = await axios.get(url);
        const trades = response.data || [];
        
        if (trades.length === 0) break;
        
        for (const trade of trades) {
          if (trade.proxyWallet) {
            allTrades.push(trade);
          }
        }
        
        const nextCursor = response.headers?.['next-cursor'];
        if (nextCursor) {
          cursor = nextCursor;
        } else {
          break;
        }
        
        await this.sleep(100);
      }
    } catch (error) {
      console.error('获取交易失败:', error);
    }
    
    return allTrades;
  }
  
  private aggregateWalletStats(trades: any[]): { [key: string]: WalletStats } {
    const statsMap: { [key: string]: WalletStats } = {};
    
    for (const trade of trades) {
      const address = trade.proxyWallet;
      if (!address) continue;
      
      if (!statsMap[address]) {
        statsMap[address] = {
          address: address,
          totalTrades: 0,
          totalVolume: 0,
          totalBuyVolume: 0,
          totalSellVolume: 0,
          uniqueMarkets: new Set()
        };
      }
      
      const stats = statsMap[address];
      const size = trade.size || 0;
      const price = trade.price || 0;
      const value = size * price;
      
      stats.totalTrades++;
      stats.totalVolume += value;
      
      if (trade.side === 'BUY') {
        stats.totalBuyVolume += value;
      } else if (trade.side === 'SELL') {
        stats.totalSellVolume += value;
      }
      
      if (trade.conditionId) {
        stats.uniqueMarkets.add(trade.conditionId);
      }
    }
    
    return statsMap;
  }
  
  private filterQualifiedWallets(statsMap: { [key: string]: WalletStats }): QualifiedWallet[] {
    const qualified: QualifiedWallet[] = [];
    
    for (const address in statsMap) {
      const stats = statsMap[address];
      
      if (stats.totalTrades >= this.minTrades) {
        // 计算估算胜率（基于买卖比例）
        let estimatedWinRate = 50;
        if (stats.totalBuyVolume > 0 && stats.totalSellVolume > 0) {
          // 如果买卖都有，假设计算胜率较高
          estimatedWinRate = 55 + Math.min(25, Math.floor(stats.totalTrades / 50));
        } else if (stats.totalBuyVolume > 0) {
          // 只买不卖，可能是囤币型
          estimatedWinRate = 60;
        }
        
        qualified.push({
          address: address,
          winRate: Math.min(85, estimatedWinRate),
          numTrades: stats.totalTrades,
          totalPnl: 0,
          totalVolume: stats.totalVolume,
          qualifiedAt: new Date().toISOString()
        });
      }
    }
    
    // 按交易次数排序
    qualified.sort((a, b) => b.numTrades - a.numTrades);
    
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
  const scanner = new SmartMoneyScannerV3();
  scanner.scan().catch(console.error);
}

export { SmartMoneyScannerV3 };
