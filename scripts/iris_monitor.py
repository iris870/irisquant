import subprocess
import json
import os
import sys

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        return str(e)

def get_pm2_status():
    stdout = run_command("pm2 jlist")
    try:
        data = json.loads(stdout)
        status_summary = []
        for process in data:
            status_summary.append({
                "name": process["name"],
                "status": process["pm2_env"]["status"],
                "restarts": process["pm2_env"]["restart_time"],
                "uptime": process["pm2_env"]["pm_uptime"]
            })
        return status_summary
    except:
        return "Error parsing PM2 list"

def get_db_size():
    return run_command("du -h /root/irisquant/data/knowledge.db")

def get_recent_logs(name, lines=20):
    return run_command(f"pm2 logs {name} --lines {lines} --no-daemon & sleep 2 && kill $!")

if __name__ == "__main__":
    report = {
        "pm2": get_pm2_status(),
        "db_size": get_db_size(),
        "learning_logs": get_recent_logs("learning", 10),
        "contract_logs": get_recent_logs("contract-trader", 10)
    }
    print(json.dumps(report, indent=2))
