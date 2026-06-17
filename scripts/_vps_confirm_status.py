import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""node -e "
const fs=require('fs');
const html=fs.readFileSync('/opt/telegramforward/static/index.html','utf8');
const m=html.match(/assets\/(app-[^\"]+\.js)/);
console.log('bundle', m[1]);
const t=fs.readFileSync('/opt/telegramforward/static/assets/'+m[1],'utf8');
const i=t.indexOf('function eo()');
const hook=t.slice(i,i+220);
console.log(hook);
console.log('patched', hook.includes('__TA_CONFIRM_VALUE__'));
console.log('Ak.Provider', (t.match(/Ak\.Provider/g)||[]).length);
console.log('lk.Provider', (t.match(/lk\.Provider/g)||[]).length);
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
