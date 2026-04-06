import subprocess
import json
import os
import sys

def run(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:
        return str(e)

def pm2_status():
    data = json.loads(run("pm2 jlist"))
    return [{"name": p["name"], "status": p["pm2_env"]["status"], "restarts": p["pm2_env"]["restart_time"]} for p in data]

def fix_all():
    # 自动识别 errored 进程并尝试重启
    for p in pm2_status():
        if p["status"] == "errored":
            run(f"pm2 restart {p['name']}")
    return "Fix complete."

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status":
        print(json.dumps({"pm2": pm2_status(), "db": run("du -h /root/irisquant/data/knowledge.db")}, indent=2))
    elif action == "fix":
        print(fix_all())
    elif action == "report":
        print(run("tail -n 20 /root/irisquant/reports/*.txt 2>/dev/null"))
