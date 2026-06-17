import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
idx = t.find("export function CandidatesPanel") 
if idx < 0:
    idx = t.find("function _Component35")
start = t.rfind("return <div className=\"cand-page\"", 0, idx + 500000)
# find last return in CandidatesPanel - search from end of file backwards for cand-page
idx2 = t.find("return <div className=\"cand-page\"", idx)
if idx2 < 0:
    idx2 = t.find('return <div className="cand-page"')
chunk = t[idx2:idx2+4500]
print(chunk.encode("ascii", "replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
