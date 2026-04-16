/**
 * 聪明钱扫描器 v2
 * 使用官方 Data API + Graph 混合策略，避免限流
 */
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';

interface QualifiedWallet {
  address: string;
  winRate: number;
  numTrades: number;
  totalPnl: number;
  totalVolume: number;
  qualifiedAt: string;
}

class SmartMoneyScannerV2 {
  private outputPath = path.join(__dirname, '../../../config/qualified-wallets.json');
  private minWinRate = 70;      // 最低胜率 70%
  private minTrades = 2;       // 最少交易 50 笔
  private maxWallets = 20;      // 最多保存 20 个钱包

  async scan(): Promise<void> {
    console.log('\n🔍 开始扫描聪明钱...\n');
    
    // 步骤1: 从官方 Data API 获取近期活跃钱包
    const activeWallets = await this.getActiveWalletsFromDataAPI();
    console.log(`📊 官方API: 发现 ${activeWallets.length} 个活跃钱包`);
    
    if (activeWallets.length === 0) {
      console.log('⚠️ 未发现活跃钱包，跳过扫描');
      return;
    }
    
    // 步骤2: 从 Graph 获取这些钱包的详细信息（只查前50个）
    const qualified: QualifiedWallet[] = [];
    const batchSize = 10;
    
    for (let i = 0; i < Math.min(activeWallets.length, 50); i += batchSize) {
      const batch = activeWallets.slice(i, i + batchSize);
      const details = await this.getWalletDetailsFromGraph(batch);
      
      for (const detail of details) {
        if (detail.winRate >= this.minWinRate && detail.numTrades >= this.minTrades) {
          qualified.push({
            address: detail.address,
            winRate: detail.winRate,
            numTrades: detail.numTrades,
            totalPnl: detail.totalPnl,
            totalVolume: detail.totalVolume,
            qualifiedAt: new Date().toISOString()
          });
        }
      }
      
      // 避免 Graph 限流：每批之间等待 2 秒
      if (i + batchSize < activeWallets.length) {
        await this.sleep(2000);
      }
    }
    
    // 按胜率排序
    qualified.sort((a, b) => b.winRate - a.winRate);
    
    // 保存
    this.saveQualifiedWallets(qualified.slice(0, this.maxWallets));
    
    console.log(`\n✅ 扫描完成，筛选出 ${qualified.length} 个合格钱包，已保存 ${Math.min(qualified.length, this.maxWallets)} 个\n`);
  }
  
  /**
   * 从官方 Data API 获取近期活跃钱包
   * 官方 API 不限流，稳定可靠
   */
  private async getActiveWalletsFromDataAPI(): Promise<string[]> {
    try {
      // 获取最近 7 天的交易
      const sevenDaysAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 3600;
      const url = `https://data-api.polymarket.com/trades?limit=2000&timestamp_gt=${sevenDaysAgo}`;
      
      const response = await axios.get(url);
      const trades = response.data || [];
      
      // 统计每个钱包的交易次数
      const walletCount: { [key: string]: number } = {};
      for (const trade of trades) {
        const wallet = trade.proxyWallet;
        if (wallet) {
          walletCount[wallet] = (walletCount[wallet] || 0) + 1;
        }
      }
      
      // 筛选交易次数 >= minTrades 的钱包
      const activeWallets = Object.entries(walletCount)
        .filter(([_, count]) => count >= this.minTrades)
        .map(([wallet]) => wallet);
      
      return activeWallets;
    } catch (error) {
      console.error('获取活跃钱包失败:', error);
      return [];
    }
  }
  
  /**
   * 从 Graph 获取钱包详细信息（胜率、盈亏等）
   * Graph 有限流，但只查少量钱包，可控
   */
  private async getWalletDetailsFromGraph(wallets: string[]): Promise<any[]> {
    if (wallets.length === 0) return [];
    
    const query = `
      query GetWallets($wallets: [String!]) {
        accounts(where: { id_in: $wallets }) {
          id
          totalRealizedPnl
          winRate
          profitFactor
          numTrades
          totalVolume
        }
      }
    `;
    
    try {
      const response = await axios.post(
        'https://api.studio.thegraph.com/query/111767/polymarket-profit-and-loss-/version/latest',
        { query, variables: { wallets } }
      );
      
      const accounts = response.data.data?.accounts || [];
      
      return accounts.map((acc: any) => ({
        address: acc.id,
        winRate: parseFloat(acc.winRate) * 100,
        numTrades: acc.numTrades,
        totalPnl: parseFloat(acc.totalRealizedPnl),
        totalVolume: parseFloat(acc.totalVolume)
      }));
    } catch (error) {
      console.error(`Graph查询失败 (${wallets.length}个钱包):`, error);
      return [];
    }
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
  const scanner = new SmartMoneyScannerV2();
  scanner.scan().catch(console.error);
}

export { SmartMoneyScannerV2 };
