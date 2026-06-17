import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)

def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=60)
    return (o.read() + e.read()).decode()

print(run("ls -la /opt/telegramforward /opt/telegramforward.old 2>/dev/null | head -5"))
print(run("pm2 describe telegram-backend 2>/dev/null | grep -E 'exec cwd|script path|interpreter'"))
print(run("grep -E '^AI_|^OPENAI_' /opt/telegramforward/.env 2>/dev/null | sed 's/=.*/=***/'"))
print(run("grep -n 'start_karthik\\|karthik_inbox_sweep' /opt/telegramforward/server.py"))
print(run("grep -n 'AI_AUTO_REPLY' /opt/telegramforward/workers/account_worker.py"))
print(run(
    "cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward "
    "/opt/telegramforward/venv/bin/python -c "
    "'import os; print(\"AI_API_KEY\", bool(os.getenv(\"AI_API_KEY\"))); "
    "import core.ai_smart_reply as a; print(\"enabled\", a.is_enabled())'"
))
print(run("grep -rn load_dotenv /opt/telegramforward --include='*.py' 2>/dev/null | sed -n '1,12p'"))
print(run("curl -s http://127.0.0.1:8000/ai/smart-reply/config -H 'Cookie: ' 2>/dev/null | head -c 200"))
ssh.close()
