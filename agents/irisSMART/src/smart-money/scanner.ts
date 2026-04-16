import axios from 'axios';
import * as fs from 'node:fs';
import * as path from 'node:path';
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
import { QualifiedWallet } from '../types';

class SmartMoneyScanner {
  private subgraphUrl = 'https://api.studio.thegraph.com/query/111767/polymarket-profit-and-loss-/version/latest';
  private minWinRate = 80;
  private minTrades = 20;

  async scanTopTraders(limit: number = 100): Promise<QualifiedWallet[]> {
    console.log(`\n🔍 开始扫描前 ${limit} 名交易者...\n`);
    
    const query = `
      query GetTopTraders($limit: Int!) {
        accounts(
          first: $limit
          orderBy: totalRealizedPnl
          orderDirection: desc
          where: { numTrades_gt: 20, isContract: false }
        ) {
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
      const response = await axios.post(this.subgraphUrl, {
        query,
        variables: { limit }
      });
      await delay(2000);

      const traders = response.data.data?.accounts || [];
      console.log(`📊 获取到 ${traders.length} 个交易者数据\n`);

      const qualified: QualifiedWallet[] = [];

      for (const trader of traders) {
        const winRate = Number.parseFloat(trader.winRate) * 100;
        
        if (winRate >= this.minWinRate && trader.numTrades >= this.minTrades) {
          qualified.push({
            address: trader.id,
            winRate: winRate,
            numTrades: trader.numTrades,
            totalPnl: Number.parseFloat(trader.totalRealizedPnl),
            totalVolume: Number.parseFloat(trader.totalVolume),
            qualifiedAt: new Date().toISOString()
          });
        }
      }

      qualified.sort((a, b) => b.winRate - a.winRate);
      this.saveQualifiedWallets(qualified);
      this.printResults(qualified);

      return qualified;

    } catch (error) {
      console.error('❌ 扫描失败:', error);
      return [];
    }
  }

  private saveQualifiedWallets(wallets: QualifiedWallet[]): void {
    const outputPath = path.join(__dirname, '../../config/qualified-wallets.json');
    const dir = path.dirname(outputPath);
    
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    fs.writeFileSync(outputPath, JSON.stringify({
      lastUpdated: new Date().toISOString(),
      count: wallets.length,
      wallets: wallets
    }, null, 2));
    
    console.log(`💾 已保存到: ${outputPath}\n`);
  }

  private printResults(wallets: QualifiedWallet[]): void {
    console.log('='.repeat(60));
    console.log(`✅ 筛选结果：共 ${wallets.length} 个胜率 >80% 的钱包\n`);
    
    wallets.slice(0, 10).forEach((wallet, i) => {
      console.log(`${i+1}. ${wallet.address.slice(0, 10)}...`);
      console.log(`   胜率: ${wallet.winRate.toFixed(1)}%`);
      console.log(`   交易次数: ${wallet.numTrades}`);
      console.log(`   PnL: $${wallet.totalPnl.toFixed(2)}`);
      console.log(`   交易量: $${(wallet.totalVolume).toFixed(2)}`);
      console.log('');
    });
    
    if (wallets.length > 10) {
      console.log(`... 还有 ${wallets.length - 10} 个钱包\n`);
    }
    console.log('='.repeat(60));
  }
}

if (require.main === module) {
  const scanner = new SmartMoneyScanner();
  scanner.scanTopTraders(100).catch(console.error);
}

export { SmartMoneyScanner };
