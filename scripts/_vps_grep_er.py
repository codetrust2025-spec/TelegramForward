import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ["VPS_PASSWORD"], timeout=30)
cmds = [
    "grep -n 'function ER' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -3",
    "sed -n '160,220p' /opt/telegramforward/dashboard/src/teleautomation-app.jsx",
    "node -e \"const fs=require('fs');const t=fs.readFileSync('/opt/telegramforward/static/assets/index-D1YMOX_o.js','utf8');const i=t.indexOf('useAuth must be used');console.log('err idx',i);const j=t.indexOf('Posting mode');console.log('posting mode',j);const k=t.match(/function TeleAutomationApp[^}]+}/);console.log(k&&k[0].slice(0,200));\"",
    "cd /opt/telegramforward/dashboard && npm run build 2>&1 | grep -i error || echo build_ok",
]
for cmd in cmds:
    print("===", cmd[:90])
    _, o, _ = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace")[:4000])
c.close()
