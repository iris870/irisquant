import axios from 'axios';
import * as fs from 'node:fs';
import * as path from 'node:path';

interface QualifiedWallet {
  address: string;
  winRate: number;
  numTrades: number;
  totalPnl: number;
  profitFactor: number;
  qualifiedAt: string;
}

async function scanTopTraders() {
  console.log('\n🔍 开始扫描 Polymarket 顶级交易者...\n');
  
  const url = 'https://api.studio.thegraph.com/query/111767/polymarket-profit-and-loss-/version/latest';
  
  const query = `
    query {
      accounts(
        first: 100
        orderBy: totalRealizedPnl
        orderDirection: desc
        where: { numTrades_gt: 20 }
      ) {
        id
        numTrades
        totalRealizedPnl
        winRate
        profitFactor
      }
    }
  `;
  
  try {
    const response = await axios.post(url, { query });
    const traders = response.data.data?.accounts || [];
    console.log(`📊 获取到 ${traders.length} 个交易者数据\n`);
    
    const qualified: QualifiedWallet[] = [];
    
    for (const trader of traders) {
      // winRate 是小数 (0.84 = 84%)，转换为百分比
      const winRate = Number.parseFloat(trader.winRate) * 100;
      // totalRealizedPnl 单位是 wei，除以 1e6 得到 USDC
      const totalPnl = Number.parseFloat(trader.totalRealizedPnl) / 1e6;
      const numTrades = Number.parseInt(trader.numTrades);
      const profitFactor = Number.parseFloat(trader.profitFactor);
      
      // 筛选条件：胜率 >= 80%，交易次数 >= 20
      if (winRate >= 80 && numTrades >= 20) {
        qualified.push({
          address: trader.id,
          winRate: winRate,
          numTrades: numTrades,
          totalPnl: totalPnl,
          profitFactor: profitFactor,
          qualifiedAt: new Date().toISOString()
        });
      }
    }
    
    // 按胜率排序
    qualified.sort((a, b) => b.winRate - a.winRate);
    
    // 保存结果
    const outputPath = path.join(__dirname, '../../config/qualified-wallets.json');
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    
    fs.writeFileSync(outputPath, JSON.stringify({
      lastUpdated: new Date().toISOString(),
      count: qualified.length,
      wallets: qualified
    }, null, 2));
    
    console.log('='.repeat(60));
    console.log(`✅ 筛选结果：共 ${qualified.length} 个胜率 >80% 的钱包\n`);
    
    if (qualified.length === 0) {
      console.log('⚠️ 没有找到符合条件的钱包\n');
    } else {
      qualified.slice(0, 10).forEach((wallet, i) => {
        console.log(`${i+1}. ${wallet.address.slice(0, 10)}...`);
        console.log(`   胜率: ${wallet.winRate.toFixed(1)}%`);
        console.log(`   交易次数: ${wallet.numTrades}`);
        console.log(`   PnL: $${wallet.totalPnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`);
        console.log(`   盈利因子: ${wallet.profitFactor.toFixed(2)}`);
        console.log('');
      });
    }
    
    console.log('='.repeat(60));
    console.log(`💾 已保存到: ${outputPath}`);
    
  } catch (error) {
    console.error('❌ 扫描失败:', error);
  }
}

scanTopTraders();
