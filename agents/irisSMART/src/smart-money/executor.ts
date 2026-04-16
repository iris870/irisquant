
import * as fs from 'node:fs';
import * as path from 'node:path';

interface TradeSignal {
  marketId: string;
  outcome: string;
  strength: number;      // 同时交易的钱包数量
  totalAmount: number;   // 总交易金额 (USDC)
  avgPrice: number;      // 平均价格
  wallets: string[];     // 参与的钱包地址
  timestamp: Date;
}

interface Position {
  marketId: string;
  outcome: string;
  amount: number;        // 持仓数量 (shares)
  entryPrice: number;
  entryTime: Date;
  status: 'open' | 'closed';
}

class CopyTradeExecutor {
  private readonly positions: Position[] = [];
  private dailyLoss: number = 0;
  private lastResetDate: string = new Date().toDateString();
  
  // 风控参数
  private readonly maxPositionSize: number = 500;      // 单笔最大 $500
  private readonly maxDailyLoss: number = 200;         // 每日最大亏损 $200
  private readonly maxConcurrentPositions: number = 5; // 最多同时持仓5个
  private readonly minSignalStrength: number = 3;      // 最少3个聪明钱同时交易
  
  constructor() {
    this.loadPositions();
    this.resetDailyLossIfNeeded();
  }

  async executeSignal(signal: TradeSignal): Promise<void> {
    console.log('\n' + '='.repeat(60));
    console.log('📊 收到跟单信号');
    console.log('='.repeat(60));
    
    // 1. 检查信号强度
    if (signal.strength < this.minSignalStrength) {
      console.log(`⚠️ 信号强度不足: ${signal.strength} < ${this.minSignalStrength}，跳过`);
      return;
    }
    
    // 2. 检查风控
    if (!this.checkRiskControls(signal)) {
      console.log('❌ 风控检查未通过，跳过跟单');
      return;
    }
    
    // 3. 计算跟单金额
    const copyAmount = this.calculateCopyAmount(signal);
    if (copyAmount < 10) {
      console.log(`⚠️ 跟单金额过小: $${copyAmount} < $10，跳过`);
      return;
    }
    
    console.log(`✅ 风控通过，准备跟单:`);
    console.log(`   📊 信号强度: ${signal.strength} 个聪明钱`);
    console.log(`   💰 跟单金额: $${copyAmount}`);
    console.log(`   🎲 方向: ${signal.outcome}`);
    
    // 4. 执行交易（模拟/实盘）
    await this.placeOrder(signal, copyAmount);
  }
  
  private checkRiskControls(signal: TradeSignal): boolean {
    // 重置每日亏损
    this.resetDailyLossIfNeeded();
    
    // 检查每日亏损上限
    if (this.dailyLoss >= this.maxDailyLoss) {
      console.log(`❌ 今日亏损已达上限: $${this.dailyLoss} / $${this.maxDailyLoss}`);
      return false;
    }
    
    // 检查最大持仓数
    const openPositions = this.positions.filter(p => p.status === 'open');
    if (openPositions.length >= this.maxConcurrentPositions) {
      console.log(`❌ 持仓已达上限: ${openPositions.length} / ${this.maxConcurrentPositions}`);
      return false;
    }
    
    // 检查是否已持有相同市场
    const existing = openPositions.find(p => p.marketId === signal.marketId);
    if (existing) {
      console.log(`❌ 已持有相同市场: ${signal.marketId}`);
      return false;
    }
    
    return true;
  }
  
  private calculateCopyAmount(signal: TradeSignal): number {
    // 按信号强度分级
    let baseAmount = 100;  // 基础金额 $100
    
    if (signal.strength >= 5) {
      baseAmount = 300;     // 强信号
    } else if (signal.strength >= 3) {
      baseAmount = 150;     // 中信号
    }
    
    // 不超过单笔上限
    return Math.min(baseAmount, this.maxPositionSize);
  }
  
  private async placeOrder(signal: TradeSignal, amount: number): Promise<void> {
    // TODO: 实现信号强度计算: 接入 Polymarket API 真实下单
    // 当前为模拟模式
    
    console.log('\n' + '🎯'.repeat(10));
    console.log('💰 执行跟单订单 (模拟模式)');
    console.log('🎯'.repeat(10));
    console.log(`   市场: ${signal.marketId}`);
    console.log(`   方向: ${signal.outcome}`);
    console.log(`   金额: $${amount}`);
    console.log(`   价格: ~$${signal.avgPrice.toFixed(4)}`);
    console.log(`   时间: ${new Date().toLocaleString()}`);
    console.log('🎯'.repeat(10) + '\n');
    
    // 记录持仓
    const position: Position = {
      marketId: signal.marketId,
      outcome: signal.outcome,
      amount: amount,
      entryPrice: signal.avgPrice,
      entryTime: new Date(),
      status: 'open'
    };
    this.positions.push(position);
    this.savePositions();
    
    // 保存信号日志
    this.saveSignalLog(signal, amount);
  }
  
  private resetDailyLossIfNeeded(): void {
    const today = new Date().toDateString();
    if (today !== this.lastResetDate) {
      this.dailyLoss = 0;
      this.lastResetDate = today;
      console.log(`📅 每日亏损已重置，新的一天: ${today}`);
    }
  }
  
  private savePositions(): void {
    const filePath = path.join(__dirname, '../../config/positions.json');
    fs.writeFileSync(filePath, JSON.stringify(this.positions, null, 2));
  }
  
  private loadPositions(): void {
    const filePath = path.join(__dirname, '../../config/positions.json');
    if (fs.existsSync(filePath)) {
      this.positions = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    }
  }
  
  private saveSignalLog(signal: TradeSignal, amount: number): void {
    const logFile = path.join(__dirname, '../../config/signal-log.json');
    let logs: { signal: TradeSignal; executedAmount: number; executedAt: string }[] = [];
    if (fs.existsSync(logFile)) {
      logs = JSON.parse(fs.readFileSync(logFile, 'utf-8'));
    }
    logs.unshift({
      signal,
      executedAmount: amount,
      executedAt: new Date().toISOString()
    });
    if (logs.length > 100) logs = logs.slice(0, 100);
    fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
  }
  
  // 记录亏损（供外部调用）
  recordLoss(amount: number): void {
    this.dailyLoss += amount;
    console.log(`⚠️ 记录亏损: $${amount}，今日累计: $${this.dailyLoss}`);
  }
  
  // 获取状态
  getStatus(): object {
    const openPositions = this.positions.filter(p => p.status === 'open');
    return {
      openPositions: openPositions.length,
      dailyLoss: this.dailyLoss,
      dailyLimit: this.maxDailyLoss,
      totalTrades: this.positions.length
    };
  }
}

export { CopyTradeExecutor, TradeSignal };
