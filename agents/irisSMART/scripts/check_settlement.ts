/**
 * 检查市场结算结果
 * 使用 Gamma API 获取已结算市场的最终结果
 */
import axios from 'axios';

async function checkMarketSettlement(marketId: string) {
  try {
    const url = `https://gamma-api.polymarket.com/markets/${marketId}`;
    const response = await axios.get(url);
    const data = response.data;
    
    const status = data.closed ? (data.outcome ? `已结算: ${data.outcome}` : '已关闭') : '进行中';
    console.log(`${data.id}: ${data.question?.substring(0, 50)}... | ${status}`);
    
    return data;
  } catch (error) {
    console.error(`获取市场 ${marketId} 失败:`, error);
    return null;
  }
}

async function main() {
  console.log('\n🔍 检查市场结算结果...\n');
  
  // 检查几个已知市场
  const markets = ['540881', '540844', '540816', '544093'];
  
  for (const id of markets) {
    await checkMarketSettlement(id);
    await new Promise(r => setTimeout(r, 500));
  }
}

main();
