import * as fs from 'node:fs';
import * as path from 'node:path';

interface Position {
  id: string;
  marketId: string;
  outcome: string;
  amount: number;
  entryPrice: number;
  entryTime: Date;
  status: 'open' | 'closed';
  stopLoss?: number;
  takeProfit?: number;
}

interface RiskConfig {
  maxPositionSize: number;
  maxDailyLoss: number;
  maxConcurrentPositions: number;
  stopLossPercent: number;
  takeProfitPercent: number;
  minWinRateToFollow: number;
  minSignalStrength: number;
}

class RiskManager {
  private readonly positions: Position[] = [];
  private dailyLoss: number = 0;
  private lastResetDate: string = new Date().toDateString();
  private config: RiskConfig;

  constructor(config?: Partial<RiskConfig>) {
    this.config = {
      maxPositionSize: 100,
      maxDailyLoss: 50,
      maxConcurrentPositions: 3,
      stopLossPercent: 0.1,
      takeProfitPercent: 0.2,
      minWinRateToFollow: 70,
      minSignalStrength: 3,
      ...config
    };
    
    this.loadPositions();
    this.resetDailyLossIfNeeded();
  }

  canOpenPosition(signalStrength: number, walletWinRate?: number): { allowed: boolean; reason?: string } {
    this.resetDailyLossIfNeeded();
    if (this.dailyLoss >= this.config.maxDailyLoss) {
      return { allowed: false, reason: `今日亏损已达上限: $${this.dailyLoss} / $${this.config.maxDailyLoss}` };
    }
    if (signalStrength < this.config.minSignalStrength) {
      return { allowed: false, reason: `信号强度不足: ${signalStrength} < ${this.config.minSignalStrength}` };
    }
    if (walletWinRate && walletWinRate < this.config.minWinRateToFollow) {
      return { allowed: false, reason: `钱包胜率不足: ${walletWinRate}% < ${this.config.minWinRateToFollow}%` };
    }
    const openPositions = this.getOpenPositions();
    if (openPositions.length >= this.config.maxConcurrentPositions) {
      return { allowed: false, reason: `持仓已达上限: ${openPositions.length} / ${this.config.maxConcurrentPositions}` };
    }
    return { allowed: true, reason: '' };
  }

  calculatePositionSize(signalStrength: number, totalAmount: number): number {
    let baseAmount = 50;
    if (signalStrength >= 5) {
      baseAmount = 100;
    } else if (signalStrength >= 3) {
      baseAmount = 50;
    }
    return Math.min(baseAmount, this.config.maxPositionSize);
  }

  calculateStopLoss(entryPrice: number, outcome: string): number {
    if (outcome === 'Yes') {
      return entryPrice * (1 - this.config.stopLossPercent);
    } else {
      return entryPrice * (1 + this.config.stopLossPercent);
    }
  }

  calculateTakeProfit(entryPrice: number, outcome: string): number {
    if (outcome === 'Yes') {
      return entryPrice * (1 + this.config.takeProfitPercent);
    } else {
      return entryPrice * (1 - this.config.takeProfitPercent);
    }
  }

  addPosition(position: Omit<Position, 'id'>): Position {
    const newPosition: Position = {
      ...position,
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      stopLoss: this.calculateStopLoss(position.entryPrice, position.outcome),
      takeProfit: this.calculateTakeProfit(position.entryPrice, position.outcome)
    };
    this.positions.push(newPosition);
    this.savePositions();
    console.log(`📊 添加持仓: ${newPosition.id} | 金额: $${newPosition.amount}`);
    return newPosition;
  }

  closePosition(positionId: string, closePrice: number, reason: string): void {
    const position = this.positions.find(p => p.id === positionId);
    if (!position || position.status === 'closed') return;
    let pnl = 0;
    if (position.outcome === 'Yes') {
      pnl = position.amount * ((closePrice - position.entryPrice) / position.entryPrice);
    } else {
      pnl = position.amount * ((position.entryPrice - closePrice) / position.entryPrice);
    }
    position.status = 'closed';
    if (pnl < 0) {
      this.dailyLoss += Math.abs(pnl);
      console.log(`❌ 平仓: 亏损 $${Math.abs(pnl).toFixed(2)} | ${reason}`);
    } else {
      console.log(`✅ 平仓: 盈利 $${pnl.toFixed(2)} | ${reason}`);
    }
    this.savePositions();
  }

  recordLoss(amount: number): void {
    this.dailyLoss += amount;
    console.log(`⚠️ 记录亏损: $${amount}，今日累计: $${this.dailyLoss}`);
  }

  getDailyLoss(): number {
    this.resetDailyLossIfNeeded();
    return this.dailyLoss;
  }

  getDailyLossLimit(): number {
    return this.config.maxDailyLoss;
  }

  getRemainingDailyBudget(): number {
    return Math.max(0, this.config.maxDailyLoss - this.dailyLoss);
  }

  getOpenPositions(): Position[] {
    return this.positions.filter(p => p.status === 'open');
  }

  getConfig(): RiskConfig {
    return { ...this.config };
  }

  updateConfig(newConfig: Partial<RiskConfig>): void {
    this.config = { ...this.config, ...newConfig };
    console.log('📊 风控配置已更新');
  }

  getStatus(): object {
    const openPositions = this.getOpenPositions();
    return {
      dailyLoss: this.dailyLoss,
      dailyLimit: this.config.maxDailyLoss,
      remainingBudget: this.getRemainingDailyBudget(),
      openPositions: openPositions.length,
      maxPositions: this.config.maxConcurrentPositions
    };
  }

  private resetDailyLossIfNeeded(): void {
    const today = new Date().toDateString();
    if (today !== this.lastResetDate) {
      this.dailyLoss = 0;
      this.lastResetDate = today;
      console.log(`📅 每日亏损已重置: ${today}`);
    }
  }

  private loadPositions(): void {
    const filePath = path.join(__dirname, '../../config/positions.json');
    if (fs.existsSync(filePath)) {
      try {
        this.positions = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      } catch (e) {
    console.warn("加载持仓失败:", e);
  }
    }
  }

  private savePositions(): void {
    const filePath = path.join(__dirname, '../../config/positions.json');
    fs.writeFileSync(filePath, JSON.stringify(this.positions, null, 2));
  }
}

export { RiskManager, RiskConfig, Position };
