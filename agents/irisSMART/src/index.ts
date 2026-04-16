import { SmartMoneyScanner } from './smart-money/scanner';
import * as dotenv from 'dotenv';

dotenv.config();

async function main() {
  console.log('\n🚀 irisSMART - 聪明钱跟单系统启动\n');
  console.log(`⏰ 启动时间: ${new Date().toLocaleString()}\n`);
  
  const scanner = new SmartMoneyScanner();
  await scanner.scanTopTraders(100);
  
  console.log('\n✨ 扫描完成！');
}

main().catch(console.error)

