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
console.log('Ak.Provider count', (t.match(/Ak\.Provider/g)||[]).length);
console.log('lk.Provider count', (t.match(/lk\.Provider/g)||[]).length);
const i=t.lastIndexOf('TeleAutomationApp');
console.log(t.slice(i, i+400));
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
