import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
_, o, _ = c.exec_command(
    "grep -n 'useConfirm must' /opt/telegramforward/dashboard/src/teleautomation-app.jsx"
)
print(o.read().decode())
_, o, _ = c.exec_command(
    "grep -n '__TA_CONFIRM' /opt/telegramforward/static/assets/index-CwCUIkUq.js; "
    "grep -o '.__TA_CONFIRM_VALUE__' /opt/telegramforward/static/assets/index-CwCUIkUq.js | head -3; "
    "node -e \"const t=require('fs').readFileSync('/opt/telegramforward/static/assets/index-CwCUIkUq.js','utf8');"
    "const i=t.indexOf('useConfirm must');console.log(t.slice(i-120,i+100));\""
)
print(o.read().decode())
c.close()
