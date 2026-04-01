module.exports = {
  apps: [
    { name: "leader", script: "/root/irisquant/venv/bin/python", args: "-m agents.leader", cwd: "/root/irisquant" },
    { name: "btc-rolling", script: "/root/irisquant/venv/bin/python", args: "-m agents.btc_rolling", cwd: "/root/irisquant" },
    { name: "contract-trader", script: "/root/irisquant/venv/bin/python", args: "-m agents.contract_trader", cwd: "/root/irisquant" },
    { name: "polymarket", script: "/root/irisquant/venv/bin/python", args: "-m agents.polymarket", cwd: "/root/irisquant" },
    { name: "news", script: "/root/irisquant/venv/bin/python", args: "-m agents.news", cwd: "/root/irisquant" },
    { name: "onchain", script: "/root/irisquant/venv/bin/python", args: "-m agents.onchain", cwd: "/root/irisquant" },
    { name: "learning", script: "/root/irisquant/venv/bin/python", args: "-m agents.learning", cwd: "/root/irisquant" },
    { name: "social", script: "/root/irisquant/venv/bin/python", args: "-m agents.social", cwd: "/root/irisquant" },
    { name: "web", script: "/root/irisquant/venv/bin/python", args: "-m uvicorn web.main:app --host 0.0.0.0 --port 8080", cwd: "/root/irisquant" }
  ]
};
