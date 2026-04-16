import axios from 'axios';

async function test() {
  const url = 'https://api.studio.thegraph.com/query/111767/polymarket-profit-and-loss-/version/latest';
  
  const query = `
    query {
      accounts(first: 10, orderBy: totalRealizedPnl, orderDirection: desc) {
        id
        numTrades
        totalRealizedPnl
        winRate
        profitFactor
      }
    }
  `;
  
  try {
    const response = await axios.post(url, { query });
    console.log(JSON.stringify(response.data, null, 2));
  } catch (error) {
    console.error('Error:', error);
  }
}

test();
