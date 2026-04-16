import { RiskManager } from '../risk/riskManager';

interface Signal {
  marketId: string;
  marketQuestion?: string;
  outcome: string;
  strength: number;
  totalAmount: number;
  avgPrice: number;
  wallets: string[];
  walletWinRates?: number[];
  timestamp: Date;
}

interface Decision {
  shouldFollow: boolean;
  action: 'BUY' | 'SELL' | 'WAIT';
  amount?: number;
  confidence: number;
  reason: string;
  suggestions?: string[];
}

class DecisionEngine {
  private riskManager: RiskManager;
  private readonly minConfidence: number = 60;

  constructor(riskManager: RiskManager) {
    this.riskManager = riskManager;
  }

  evaluate(signal: Signal): Decision {
    console.log('\n🤔 决策引擎评估信号...');

    let confidence = 0;
    const reasons: string[] = [];
    const suggestions: string[] = [];

    let strengthScore = 0;
    if (signal.strength >= 5) {
      strengthScore = 30;
      reasons.push(`✅ 强信号: ${signal.strength}个聪明钱`);
      suggestions.push('🔥 强烈建议跟单');
    } else if (signal.strength >= 3) {
      strengthScore = 20;
      reasons.push(`✅ 中信号: ${signal.strength}个聪明钱`);
      suggestions.push('✅ 可考虑跟单');
    } else {
      strengthScore = 10;
      reasons.push(`⚠️ 弱信号: ${signal.strength}个聪明钱`);
    }

    let amountScore = 0;
    if (signal.totalAmount >= 50000) {
      amountScore = 20;
      reasons.push(`💰 大额交易: $${(signal.totalAmount/1000).toFixed(0)}k`);
    } else if (signal.totalAmount >= 10000) {
      amountScore = 15;
      reasons.push(`💰 中额交易: $${(signal.totalAmount/1000).toFixed(0)}k`);
    } else {
      amountScore = 10;
      reasons.push(`💵 小额交易: $${signal.totalAmount.toLocaleString()}`);
    }

    let walletScore = 0;
    if (signal.walletWinRates && signal.walletWinRates.length > 0) {
      const avgWinRate = signal.walletWinRates.reduce((a,b) => a + b, 0) / signal.walletWinRates.length;
      if (avgWinRate >= 85) {
        walletScore = 30;
        reasons.push(`🏆 高胜率钱包: ${avgWinRate.toFixed(1)}%`);
      } else if (avgWinRate >= 75) {
        walletScore = 20;
        reasons.push(`📈 中等胜率: ${avgWinRate.toFixed(1)}%`);
      } else {
        walletScore = 10;
        reasons.push(`📊 普通胜率: ${avgWinRate.toFixed(1)}%`);
      }
    } else {
      walletScore = 15;
      reasons.push(`👛 ${signal.wallets.length}个钱包参与`);
    }

    let priceScore = 0;
    if (signal.avgPrice >= 0.4 && signal.avgPrice <= 0.6) {
      priceScore = 20;
      reasons.push(`💰 价格合理: $${signal.avgPrice.toFixed(3)}`);
    } else if (signal.avgPrice >= 0.3 && signal.avgPrice <= 0.7) {
      priceScore = 15;
      reasons.push(`💵 价格可接受: $${signal.avgPrice.toFixed(3)}`);
    } else {
      priceScore = 10;
      reasons.push(`📊 价格: $${signal.avgPrice.toFixed(3)}`);
    }

    confidence = strengthScore + amountScore + walletScore + priceScore;

    const avgWinRate = signal.walletWinRates 
      ? signal.walletWinRates.reduce((a,b) => a + b, 0) / signal.walletWinRates.length 
      : undefined;
    
    const riskCheck = this.riskManager.canOpenPosition(signal.strength, avgWinRate);
    
    if (!riskCheck.allowed) {
      return {
        shouldFollow: false,
        action: 'WAIT',
        confidence: confidence,
        reason: riskCheck.reason || '风控检查未通过',
        suggestions: ['⏸️ 等待风控条件满足']
      };
    }

    let shouldFollow = false;
    let action: 'BUY' | 'SELL' | 'WAIT' = 'WAIT';
    let finalReason = '';

    if (confidence >= this.minConfidence && signal.strength >= 3) {
      shouldFollow = true;
      action = 'BUY';
      finalReason = `信号质量优秀，信心度 ${confidence}%`;
      suggestions.push(`🎯 建议跟单金额: $${this.riskManager.calculatePositionSize(signal.strength, signal.totalAmount)}`);
    } else if (confidence >= 50 && signal.strength >= 3) {
      shouldFollow = true;
      action = 'BUY';
      finalReason = `信号质量良好，信心度 ${confidence}%`;
      suggestions.push(`💡 小仓位跟单: $${this.riskManager.calculatePositionSize(signal.strength, signal.totalAmount)}`);
    } else {
      shouldFollow = false;
      finalReason = `信号质量不足，信心度 ${confidence}%`;
      suggestions.push(`⏸️ 等待更强信号`);
    }

    console.log(`   信心度: ${confidence}%`);
    console.log(`   决策: ${shouldFollow ? '✅ 跟单' : '❌ 不跟单'}`);
    console.log(`   原因: ${finalReason}`);

    return {
      shouldFollow,
      action,
      amount: shouldFollow ? this.riskManager.calculatePositionSize(signal.strength, signal.totalAmount) : undefined,
      confidence,
      reason: finalReason,
      suggestions
    };
  }

  setMinConfidence(confidence: number): void {
    this.minConfidence = Math.max(0, Math.min(100, confidence));
  }

  getStatus(): object {
    return {
      minConfidence: this.minConfidence,
      riskStatus: this.riskManager.getStatus()
    };
  }
}

export { DecisionEngine, Signal, Decision };
