import { CopyTradeExecutor, TradeSignal } from './src/smart-money/executor';

async function test() {
  const executor = new CopyTradeExecutor();
  
  // 模拟一个强信号
  const signal: TradeSignal = {
    marketId: "0x1234567890abcdef",
    outcome: "Yes",
    strength: 5,
    totalAmount: 50000,
    avgPrice: 0.65,
    wallets: ["0xabc...", "0xdef...", "0x123..."],
    timestamp: new Date()
  };
  
  console.log('🧪 测试跟单执行器\n');
  await executor.executeSignal(signal);
  
  console.log('\n📊 当前状态:');
  console.log(executor.getStatus());
}

test();
