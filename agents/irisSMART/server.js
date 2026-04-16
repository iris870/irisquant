const express = require('express');
const path = require('path');
const app = express();
const PORT = 3000;

app.use(express.static('public'));

// 改用 :any 捕获所有路由
app.get('/(.*)', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🌐 irisSMART 已启动: http://0.0.0.0:${PORT}/smart-money`);
});
