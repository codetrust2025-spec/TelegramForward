import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n 'def install\\|@app\\|router' /opt/telegramforward.old/core/voice*.py 2>/dev/null | head -30",
    "grep -n 'analytics' /opt/telegramforward.old/services/voice_call_service.py | head -20",
    "sed -n '460,520p' /opt/telegramforward.old/services/voice_call_service.py",
    "grep -n voice /opt/telegramforward.old/server.py | head -30",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:2000])
c.close()
