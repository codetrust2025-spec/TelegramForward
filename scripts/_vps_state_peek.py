import json, os, paramiko
PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=PWD, timeout=30)
_, o, e = c.exec_command("curl -s -w '\\nHTTP:%{http_code}' http://127.0.0.1:8000/state", timeout=45)
raw = o.read().decode()
if "HTTP:" in raw:
    body, code = raw.rsplit("HTTP:", 1)
    print("http", code.strip())
    raw = body
try:
    d = json.loads(raw)
except Exception as ex:
    print("json error", ex, raw[:500])
    raise
print("keys", sorted(d.keys())[:20])
print("account_info", list((d.get("account_info") or {}).keys()))
print("account_states", list((d.get("account_states") or {}).keys())[:15])
st = d.get("account_states") or {}
for slot in list(st.keys())[:3]:
    print(slot, {k: st[slot].get(k) for k in ("running", "cycle", "success", "failed", "posting_mode")})
c.close()
