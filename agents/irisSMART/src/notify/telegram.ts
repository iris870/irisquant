
interface TradeAlert {
  trader: string;
  winRate?: number;
  marketId: string;
  outcome: string;
  amount: number;
  price: number;
  timestamp: string;
  transactionHash: string;
}

interface SignalAlert {
  strength: number;
  outcome: string;
  totalAmount: number;
  wallets: string[];
  timestamp: Date;
}

class TelegramNotifier {
  private readonly botToken: string;
  private readonly chatId: string;
  private readonly enabled: boolean = false;

  constructor() {
    // 从环境变量读取配置
    this.botToken = process.env.TELEGRAM_BOT_TOKEN || '';
    this.chatId = process.env.TELEGRAM_CHAT_ID || '';
    
    if (this.botToken && this.chatId) {
      this.enabled = true;
      console.log('✅ Telegram 通知已启用');
    } else {
      console.log('⚠️ Telegram 未配置，跳过通知');
      console.log('   设置环境变量: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID');
    }
  }

  private async sendMessage(text: string): Promise<void> {
    if (!this.enabled) return;
    
    const url = `https://api.telegram.org/bot${this.botToken}/sendMessage`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: this.chatId,
          text: text,
          parse_mode: 'HTML',
          disable_web_page_preview: true
        })
      });
      
      if (!response.ok) {
        console.error('Telegram 发送失败:', await response.text());
      }
    } catch (error) {
      console.error('Telegram 发送错误:', error);
    }
  }

  async sendTradeAlert(trade: TradeAlert): Promise<void> {
    if (!this.enabled) return;
    
    const message = `
🔔 <b>聪明钱交易警报</b>

👛 钱包: <code>${trade.trader.slice(0, 10)}...${trade.trader.slice(-6)}</code>
${trade.winRate ? `📈 胜率: <b>${trade.winRate.toFixed(1)}%</b>` : ''}
🎲 方向: <b>${trade.outcome}</b>
💰 金额: <b>$${trade.amount.toLocaleString()}</b>
💵 价格: $${trade.price.toFixed(4)}
⏰ 时间: ${trade.timestamp}
🔗 <a href="https://polygonscan.com/tx/${trade.transactionHash}">查看交易</a>
`;
    
    await this.sendMessage(message);
  }

  async sendSignalAlert(signal: SignalAlert): Promise<void> {
    if (!this.enabled) return;
    
    let strengthEmoji: string;
    if (signal.strength >= 5) {
      strengthEmoji = '🔴';
    } else if (signal.strength >= 3) {
      strengthEmoji = '🟡';
    } else {
      strengthEmoji = '🟢';
    }
    const walletsList = signal.wallets.map(w => `<code>${w.slice(0, 8)}...</code>`).join(', ');
    
    const message = `
${strengthEmoji} <b>强信号检测！</b>

📊 信号强度: <b>${signal.strength}</b> 个聪明钱同时交易
🎲 方向: <b>${signal.outcome}</b>
💰 总金额: <b>$${signal.totalAmount.toLocaleString()}</b>
👛 参与钱包: ${walletsList}

let suggestion: string;
    if (signal.strength >= 5) {
      suggestion = '🔥 强烈建议跟单';
    } else if (signal.strength >= 3) {
      suggestion = '✅ 可考虑跟单';
    } else {
      suggestion = '⚠️ 谨慎观察';
    }
    💡 建议: ${suggestion}
⏰ 时间: ${signal.timestamp.toLocaleString()}
`;
    
    await this.sendMessage(message);
  }

  async sendDailyReport(stats: {
    totalSignals: number;
    wins: number;
    losses: number;
    winRate: number;
    totalProfit: number;
  }): Promise<void> {
    if (!this.enabled) return;
    
    const message = `
📊 <b>每日信号统计报告</b>

📈 总信号数: ${stats.totalSignals}
✅ 盈利: ${stats.wins}
❌ 亏损: ${stats.losses}
🎯 胜率: <b>${stats.winRate.toFixed(1)}%</b>
💰 总盈亏: <b>$${stats.totalProfit.toFixed(2)}</b>
`;
    
    await this.sendMessage(message);
  }

  async sendStartupMessage(): Promise<void> {
    if (!this.enabled) return;
    
    const message = `
🤖 <b>irisSMART 监控系统已启动</b>

⏰ 启动时间: ${new Date().toLocaleString()}
👛 监控钱包: 15 个聪明钱
🔄 检查间隔: 30 秒
📡 状态: <b>运行中</b>
`;
    
    await this.sendMessage(message);
  }
}

export { TelegramNotifier, TradeAlert, SignalAlert };
