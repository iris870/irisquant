import { config as dotenvConfig } from "dotenv";
dotenvConfig();

interface Market {
    id: string;
    question: string;
    conditionId: string;
    clobTokenIds: string[];
    outcomes: string[];
    endDate: string;
    volume: number;
    volume24hr: number;
    bestBid: string;
    bestAsk: string;
}

async function getMarkets(limit: number = 20): Promise<Market[]> {
    const url = `https://gamma-api.polymarket.com/markets?limit=${limit}&closed=false`;
    
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Gamma API error: ${response.status}`);
    }
    
    const data = await response.json();
    return data.map((m: any) => ({
        id: m.id,
        question: m.question,
        conditionId: m.conditionId,
        clobTokenIds: typeof m.clobTokenIds === 'string' ? JSON.parse(m.clobTokenIds) : (m.clobTokenIds || []),
        outcomes: m.outcomes || [],
        endDate: m.endDateIso || m.endDate || "未知",
        volume: m.volume || 0,
        volume24hr: m.volume24hr || 0,
        bestBid: m.bestBid || "N/A",
        bestAsk: m.bestAsk || "N/A"
    }));
}

async function main() {
    console.log("📊 获取活跃市场...\n");
    
    const markets = await getMarkets(5);
    
    console.log(`找到 ${markets.length} 个活跃市场:\n`);
    
    markets.forEach((market, i) => {
        console.log(`[${i + 1}] ${market.question}`);
        console.log(`    ID: ${market.id}`);
        console.log(`    截止: ${market.endDate}`);
        console.log(`    24h交易量: $${market.volume24hr.toLocaleString()}`);
        console.log(`    最优买价: ${market.bestBid}`);
        console.log(`    最优卖价: ${market.bestAsk}`);
        
        if (market.clobTokenIds.length >= 2) {
            console.log(`    ✅ ${market.outcomes[0] || "YES"} Token ID: ${market.clobTokenIds[0]}`);
            console.log(`    ❌ ${market.outcomes[1] || "NO"} Token ID:  ${market.clobTokenIds[1]}`);
        } else if (market.clobTokenIds.length === 1) {
            console.log(`    Token ID: ${market.clobTokenIds[0]}`);
        }
        console.log("");
    });
    
    // 返回第一个市场的 token_id 供后续测试使用
    if (markets.length > 0 && markets[0].clobTokenIds.length > 0) {
        console.log("💡 提示: 第一个市场的 YES Token ID 可用于订单簿测试");
        console.log(`   Token: ${markets[0].clobTokenIds[0]}`);
    }
}

main().catch(console.error);
