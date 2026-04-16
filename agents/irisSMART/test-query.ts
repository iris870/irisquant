import axios from 'axios';

async function test() {
  const url = 'https://api.studio.thegraph.com/query/111767/polymarket-profit-and-loss-/version/latest';
  
  // 简单查询：只获取前5个账户，不设过滤
  const query = `
    query {
      accounts(first: 5) {
        id
        numTrades
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
