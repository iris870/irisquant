import axios from 'axios';

async function test() {
  console.log('🔌 测试 Polymarket 公开 API (不需要认证)\n');
  
  try {
    // 1. 获取市场列表
    console.log('📊 获取市场列表...');
    const marketsRes = await axios.get('https://gamma-api.polymarket.com/markets', {
      params: { limit: 5, closed: false }
    });
    
    const markets = marketsRes.data;
    console.log(`✅ 获取到 ${markets.length} 个活跃市场\n`);
    
    // 2. 显示前3个市场
    console.log('📈 示例市场:');
    for (let i = 0; i < Math.min(3, markets.length); i++) {
      const m = markets[i];
      console.log(`   ${i+1}. ${m.question || m.title || 'N/A'}`);
      console.log(`      市场ID: ${m.id}`);
      console.log(`      结束时间: ${m.endDate || 'N/A'}`);
      console.log('');
    }
    
    // 3. 测试价格数据
    console.log('💵 获取价格数据...');
    // 使用 Polymarket CLOB API 获取 BTC 价格市场的订单簿
    // 这是公开 API，不需要认证
    const priceRes = await axios.get('https://clob.polymarket.com/prices');
    console.log(`✅ 价格数据获取成功`);
    
  } catch (error: any) {
    console.log(`❌ 请求失败: ${error.message}`);
  }
}

test();
