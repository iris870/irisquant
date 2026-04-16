import * as fs from 'node:fs';
import * as path from 'node:path';

interface SignalRecord {
  id: string;
  marketId: string;
  marketQuestion?: string;
  outcome: string;
  strength: number;
  totalAmount: number;
  avgPrice: number;
  wallets: string[];
  timestamp: Date;
  detectedAt: string;
  resolved?: boolean;
  actualOutcome?: string;
  isWin?: boolean;
  finalPrice?: number;
  profit?: number;
}

interface StatsSummary {
  totalSignals: number;
  resolved: number;
  pending: number;
  wins: number;
  losses: number;
  winRate: number;
  totalProfit: number;
  avgProfit: number;
  strongSignalsWinRate: number;
  lastUpdate: string;
}

class SignalStatsReporter {
  private readonly signalsFile: string;
  private readonly reportsDir: string;

  constructor() {
    this.signalsFile = path.join(__dirname, '../../config/signal-stats.json');
    this.reportsDir = path.join(__dirname, '../../reports');
    
    if (!fs.existsSync(this.reportsDir)) {
      fs.mkdirSync(this.reportsDir, { recursive: true });
    }
  }

  saveSignal(signal: Omit<SignalRecord, 'id' | 'detectedAt'>): void {
    const signals = this.loadSignals();
    
    const newSignal: SignalRecord = {
      ...signal,
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      detectedAt: new Date().toISOString(),
      timestamp: new Date()
    };
    
    signals.unshift(newSignal);
    
    if (signals.length > 500) {
      signals.pop();
    }
    
    fs.writeFileSync(this.signalsFile, JSON.stringify(signals, null, 2));
    console.log(`📊 信号已记录: ${newSignal.marketId.slice(0, 20)}... | 强度: ${signal.strength}`);
  }

  loadSignals(): SignalRecord[] {
    if (fs.existsSync(this.signalsFile)) {
      const data = JSON.parse(fs.readFileSync(this.signalsFile, 'utf-8'));
      return data.map((s: SignalRecord) => ({
        ...s,
        timestamp: new Date(s.timestamp),
        detectedAt: s.detectedAt
      }));
    }
    return [];
  }

  getSummary(): StatsSummary {
    const signals = this.loadSignals();
    const resolved = signals.filter(s => s.resolved);
    const wins = resolved.filter(s => s.isWin).length;
    // const losses = resolved.filter(s => !s.isWin).length; // 未使用，保留供将来分析
    
    const totalProfit = resolved.reduce((sum, s) => sum + (s.profit || 0), 0);
    const avgProfit = resolved.length > 0 ? totalProfit / resolved.length : 0;
    
    const strongResolved = resolved.filter(s => s.strength >= 5);
    const strongWins = strongResolved.filter(s => s.isWin).length;
    const strongWinRate = strongResolved.length > 0 ? (strongWins / strongResolved.length * 100) : 0;
    
    return {
      totalSignals: signals.length,
      resolved: resolved.length,
      pending: signals.length - resolved.length,
      wins,
      losses,
      winRate: resolved.length > 0 ? (wins / resolved.length * 100) : 0,
      totalProfit,
      avgProfit,
      strongSignalsWinRate: strongWinRate,
      lastUpdate: new Date().toISOString()
    };
  }

  generateDailyReport(): string {
    const signals = this.loadSignals();
    const today = new Date().toDateString();
    const todaySignals = signals.filter(s => 
      new Date(s.detectedAt).toDateString() === today
    );
    
    const resolvedToday = todaySignals.filter(s => s.resolved);
    const wins = resolvedToday.filter(s => s.isWin).length;
    const losses = resolvedToday.filter(s => !s.isWin).length;
    const winRate = resolvedToday.length > 0 ? (wins / resolvedToday.length * 100) : 0;
    const totalProfit = resolvedToday.reduce((sum, s) => sum + (s.profit || 0), 0);
    
    const report = `
╔══════════════════════════════════════════════════════════════╗
║                    📊 每日信号统计报告                        ║
╠══════════════════════════════════════════════════════════════╣
║ 日期: ${today.padEnd(50)}║
║ 总信号数: ${String(todaySignals.length).padEnd(48)}║
║ 已结算: ${String(resolvedToday.length).padEnd(50)}║
║ 盈利: ${String(wins).padEnd(52)}║
║ 亏损: ${String(losses).padEnd(52)}║
║ 胜率: ${winRate.toFixed(1)}%${' '.repeat(52 - winRate.toFixed(1).length)}║
║ 总盈亏: $${totalProfit.toFixed(2)}${' '.repeat(48 - totalProfit.toFixed(2).length)}║
╚══════════════════════════════════════════════════════════════╝
`;
    
    const reportFile = path.join(this.reportsDir, `report-${new Date().toISOString().split('T')[0]}.txt`);
    fs.writeFileSync(reportFile, report);
    console.log(report);
    console.log(`💾 报告已保存: ${reportFile}`);
    
    return report;
  }

  generateWeeklyReport(): string {
    const signals = this.loadSignals();
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    
    const weekSignals = signals.filter(s => new Date(s.detectedAt) > oneWeekAgo);
    const resolved = weekSignals.filter(s => s.resolved);
    const wins = resolved.filter(s => s.isWin).length;
    // const losses = resolved.filter(s => !s.isWin).length; // 未使用，保留供将来分析
    const winRate = resolved.length > 0 ? (wins / resolved.length * 100) : 0;
    const totalProfit = resolved.reduce((sum, s) => sum + (s.profit || 0), 0);
    
    const strongSignals = weekSignals.filter(s => s.strength >= 5);
    const mediumSignals = weekSignals.filter(s => s.strength >= 3 && s.strength < 5);
    
    const report = `
╔══════════════════════════════════════════════════════════════╗
║                    📊 周度信号统计报告                        ║
╠══════════════════════════════════════════════════════════════╣
║ 周期: ${oneWeekAgo.toLocaleDateString()} - ${new Date().toLocaleDateString()}║
║ 总信号数: ${String(weekSignals.length).padEnd(48)}║
║ 强信号(≥5): ${String(strongSignals.length).padEnd(47)}║
║ 中信号(≥3): ${String(mediumSignals.length).padEnd(47)}║
║ 已结算: ${String(resolved.length).padEnd(50)}║
║ 胜率: ${winRate.toFixed(1)}%${' '.repeat(52 - winRate.toFixed(1).length)}║
║ 总盈亏: $${totalProfit.toFixed(2)}${' '.repeat(48 - totalProfit.toFixed(2).length)}║
╚══════════════════════════════════════════════════════════════╝
`;
    
    const reportFile = path.join(this.reportsDir, `weekly-${new Date().toISOString().split('T')[0]}.txt`);
    fs.writeFileSync(reportFile, report);
    console.log(report);
    return report;
  }

  printRecentSignals(limit: number = 10): void {
    const signals = this.loadSignals();
    const recent = signals.slice(0, limit);
    
    console.log('\n📋 最近信号列表:');
    console.log('='.repeat(80));
    
    for (const s of recent) {
      const status = s.resolved 
        ? (s.isWin ? '✅ 盈利' : '❌ 亏损')
        : '⏳ 待结算';
      
      console.log(`${s.detectedAt.slice(0, 16)} | 强度:${s.strength} | ${s.outcome} | ${status} | 跟单${s.profit ? '$' + s.profit.toFixed(2) : '等待'}`);
    }
    console.log('='.repeat(80));
  }
}

if (require.main === module) {
  const reporter = new SignalStatsReporter();
  
  console.log('\n📊 信号统计报告\n');
  
  const summary = reporter.getSummary();
  console.log('当前统计:');
  console.log(`  总信号数: ${summary.totalSignals}`);
  console.log(`  已结算: ${summary.resolved}`);
  console.log(`  胜率: ${summary.winRate.toFixed(1)}%`);
  console.log(`  总盈亏: $${summary.totalProfit.toFixed(2)}`);
  console.log(`  平均盈亏: $${summary.avgProfit.toFixed(2)}`);
  console.log(`  强信号胜率: ${summary.strongSignalsWinRate.toFixed(1)}%`);
  
  reporter.printRecentSignals(10);
  reporter.generateDailyReport();
}

export { SignalStatsReporter, SignalRecord };
