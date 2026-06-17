import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""node -e "
const fs=require('fs');
const t=fs.readFileSync('/opt/telegramforward/static/assets/app-DuSZ09ut.js','utf8');
const m=[...t.matchAll(/(\w+)=k\.createContext\(null\)/g)].map(x=>x[1]);
console.log('k contexts', m.slice(0,20));
const i=t.indexOf('Ak=k.createContext');
console.log('Ak def', t.slice(i, i+120));
const j=t.indexOf('function ik(');
console.log('ik at', j);
// TeleAutomationApp export
const k=t.lastIndexOf('function TeleAutomationApp');
console.log('export', t.slice(k, k+280));
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
