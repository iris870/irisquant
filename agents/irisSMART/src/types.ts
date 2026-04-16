export interface Trader {
  id: string;
  totalRealizedPnl: string;
  winRate: string;
  profitFactor: string;
  numTrades: number;
  totalVolume: string;
}

export interface QualifiedWallet {
  address: string;
  winRate: number;
  numTrades: number;
  totalPnl: number;
  totalVolume: number;
  qualifiedAt: string;
}
