import json
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)

cmds = [
    "curl -s http://127.0.0.1:8000/ai/smart-reply/config",
    'curl -s -X POST http://127.0.0.1:8000/ai/smart-reply/catch-up -H "Content-Type: application/json" -d \'{"max_replies":15}\'',
    "sleep 25 && curl -s http://127.0.0.1:8000/ai/smart-reply/config",
]
for cmd in cmds:
    print(">>>", cmd)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=180)
    raw = stdout.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        if "health" in data:
            h = data["health"]
            print(
                "api_key_present:", h.get("api_key_present"),
                "pending:", h.get("pending_inbound"),
                "sweep:", h.get("inbox_sweep"),
            )
        else:
            print(json.dumps(data, indent=2)[:3000])
    except json.JSONDecodeError:
        print(raw[:3000])
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)

stdin, stdout, stderr = client.exec_command(
    "pm2 logs telegram-backend --lines 120 --nostream 2>&1 | grep -iE 'ai_smart|karthik_inbox|enqueued|skip schedule' | tail -25",
    timeout=60,
)
print("\n>>> logs")
print(stdout.read().decode("utf-8", errors="replace"))

client.close()
