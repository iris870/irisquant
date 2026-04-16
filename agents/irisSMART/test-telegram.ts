import * as dotenv from 'dotenv';
import { TelegramNotifier } from './src/notify/telegram';

dotenv.config();

async function test() {
  console.log('📱 测试 Telegram 通知...\n');
  
  const notifier = new TelegramNotifier();
  
  // 发送启动消息
  await notifier.sendStartupMessage();
  
  // 发送测试交易警报
  await notifier.sendTradeAlert({
    trader: "0x7fb7ad0d194d7123e711e7db6c9d418fac14e33d",
    winRate: 84.1,
    marketId: "0x1234567890abcdef",
    outcome: "Yes",
    amount: 10000,
    price: 0.65,
    timestamp: new Date().toLocaleString(),
    transactionHash: "0xabc123def456"
  });
  
  // 发送测试强信号
  await notifier.sendSignalAlert({
    strength: 5,
    outcome: "Yes",
    totalAmount: 50000,
    wallets: ["0x7fb7ad0d", "0xd1c76931", "0xfffe4013"],
    timestamp: new Date()
  });
  
  console.log('\n✅ 测试完成，请检查你的 Telegram 是否收到消息');
}

test();
