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
// ConfirmProvider from ConfirmContext - search sk or rd assignment
const idx=t.indexOf('globalThis[rd]=');
console.log('set global value', idx, t.slice(idx, idx+200));
const idx2=t.indexOf('function sk()');
console.log('sk', t.slice(idx2, idx2+300));
// inline confirm provider uv
const idx3=t.indexOf('uv.Provider');
console.log('uv.Provider', t.slice(idx3-100, idx3+150));
" """,
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
