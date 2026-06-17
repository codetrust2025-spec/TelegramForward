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
let n=0, i=0;
while((i=t.indexOf('__TA_CONFIRM_VALUE__',i+1))>=0 && n<5){
  console.log('---',n, t.slice(Math.max(0,i-80), i+120));
  n++;
}
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
