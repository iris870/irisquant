import { RiskManager } from './src/risk/riskManager';
import { DecisionEngine } from './src/strategy/decisionEngine';

async function test() {
  console.log('\n🧪 测试风控模块 + 决策引擎\n');
  console.log('='.repeat(60));

  const riskManager = new RiskManager({
    maxPositionSize: 100,
    maxDailyLoss: 50,
    maxConcurrentPositions: 3,
    stopLossPercent: 0.1,
    takeProfitPercent: 0.2,
    minWinRateToFollow: 70,
    minSignalStrength: 3
  });

  console.log('📊 风控配置:');
  console.log(riskManager.getConfig());

  const engine = new DecisionEngine(riskManager);

  console.log('\n📡 测试信号1: 强信号 (5个聪明钱)');
  const signal1 = {
    marketId: '0x123',
    outcome: 'Yes',
    strength: 5,
    totalAmount: 100000,
    avgPrice: 0.55,
    wallets: ['0xabc', '0xdef', '0x123', '0x456', '0x789'],
    walletWinRates: [90, 85, 88, 92, 86],
    timestamp: new Date()
  };
  
  const decision1 = engine.evaluate(signal1);
  console.log('\n🎯 决策结果:');
  console.log(`   是否跟单: ${decision1.shouldFollow}`);
  console.log(`   金额: $${decision1.amount || 0}`);
  console.log(`   信心度: ${decision1.confidence}%`);
  console.log(`   原因: ${decision1.reason}`);

  console.log('\n📡 测试信号2: 弱信号 (2个聪明钱)');
  const signal2 = {
    marketId: '0x456',
    outcome: 'No',
    strength: 2,
    totalAmount: 5000,
    avgPrice: 0.3,
    wallets: ['0xabc', '0xdef'],
    walletWinRates: [65, 60],
    timestamp: new Date()
  };
  
  const decision2 = engine.evaluate(signal2);
  console.log('\n🎯 决策结果:');
  console.log(`   是否跟单: ${decision2.shouldFollow}`);
  console.log(`   金额: $${decision2.amount || 0}`);
  console.log(`   信心度: ${decision2.confidence}%`);

  console.log('\n📊 风控状态:');
  console.log(riskManager.getStatus());
}

test();

