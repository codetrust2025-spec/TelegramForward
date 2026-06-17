import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""node -e "
const t=require('fs').readFileSync('/opt/telegramforward/static/assets/app-DuSZ09ut.js','utf8');
let n=0,i=0;
while((i=t.indexOf('function eo()',i+1))>=0){
  console.log(n, t.slice(i,i+180));
  n++;
}
console.log('useConfirm throws', (t.match(/useConfirm must be used within ConfirmProvider/g)||[]).length);
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
