import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""node -e "
const fs=require('fs');
const p='/opt/telegramforward/static/assets/app-DuSZ09ut.js';
const t=fs.readFileSync(p,'utf8');
const i=t.indexOf('function eo()');
console.log('idx',i);
console.log(t.slice(i,i+220));
const m=t.match(/(\w+)=k\.createContext\(null\);function eo\(\)/);
console.log('ctx',m&&m[1]);
console.log('has global in eo', t.slice(i,i+220).includes('__TA_CONFIRM_VALUE__'));
console.log('ConfirmProvider count', (t.match(/ConfirmProvider/g)||[]).length);
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
_, o, _ = c.exec_command(
    "sed -n '1110,1125p' /opt/telegramforward/dashboard/src/teleautomation-app.jsx",
    timeout=30,
)
print("source useConfirm:")
print(o.read().decode("utf-8", errors="replace"))
c.close()
