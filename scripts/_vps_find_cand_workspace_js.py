import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
for js in pathlib.Path("/opt/telegramforward").rglob("*.js"):
    try:
        t = js.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if "cand-workspace" in t:
        print(js, t.count("cand-workspace"))
        idx = t.find("cand-workspace")
        print(t[max(0,idx-300):idx+800].encode("ascii","replace").decode()[:900])
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace")[:5000])
c.close()
