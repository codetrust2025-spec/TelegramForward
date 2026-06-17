#!/usr/bin/env python3
"""Fix campaign posting: shared AccountState fields via feature_runtime aliases."""
import base64, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FEATURE_RUNTIME = b'''"""Proxy views over prefixed AccountState fields (campaign_* / forwarding_*)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workers.account_state import AccountState


class FeatureRuntimeProxy:
    """Maps short names (cycle, success) to prefixed storage on AccountState."""

    def __init__(
        self,
        account: AccountState,
        prefix: str,
        aliases: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "_account", account)
        object.__setattr__(self, "_prefix", prefix)
        object.__setattr__(self, "_aliases", aliases or {})

    def _key(self, name: str) -> str:
        return self._aliases.get(name, f"{self._prefix}{name}")

    def __getattr__(self, name: str):
        return getattr(self._account, self._key(name))

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._account, self._key(name), value)


# Fields stored on AccountState without campaign_/forwarding_ prefix.
_SHARED_ALIASES = {
    "heavy_rate_limit": "heavy_rate_limit",
    "health_score": "health_score",
    "flood_streak": "flood_streak",
    "delay_multiplier": "delay_multiplier",
    "my_groups": "my_groups",
    "cycle_metrics": "cycle_metrics",
    "execution_policy": "execution_policy",
    "speed_profile": "speed_profile",
}

_FORWARDING_ALIASES = {
    **_SHARED_ALIASES,
    "forward_batch": "forwarding_batch",
    "forward_batch_total": "forwarding_batch_total",
    "forward_batch_size": "forwarding_batch_size",
    "forward_joined_total": "forwarding_joined_total",
    "failed_list": "forwarding_failed_list",
    "failure_counts": "forwarding_failure_counts",
}


def campaign_runtime(account: AccountState) -> FeatureRuntimeProxy:
    return FeatureRuntimeProxy(account, "campaign_", dict(_SHARED_ALIASES))


def forwarding_runtime(account: AccountState) -> FeatureRuntimeProxy:
    return FeatureRuntimeProxy(account, "forwarding_", _FORWARDING_ALIASES)
'''

PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

b64 = base64.b64encode(FEATURE_RUNTIME).decode()
c.exec_command(
    f"echo {b64} | base64 -d > /opt/telegramforward.old/workers/feature_runtime.py",
    timeout=30,
)
_, stdout, stderr = c.exec_command(
    "cd /opt/telegramforward.old && ./venv/bin/python3 -m py_compile workers/feature_runtime.py && echo OK",
    timeout=30,
)
print("compile:", stdout.read().decode(), stderr.read().decode())

clean = r'''
import pathlib, py_compile, re
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
pat = r"\n            try:\n                import traceback\n                with open\(\"/tmp/cycle_err\.log\".*?\n            except Exception:\n                pass"
src2 = re.sub(pat, "", src, flags=re.DOTALL)
pat2 = r"\n                try:\n                    import traceback\n                    with open\(\"/tmp/cycle_err\.log\".*?\n                except Exception:\n                    pass"
src2 = re.sub(pat2, "", src2, flags=re.DOTALL)
if src2 != src:
    p.write_text(src2, encoding="utf-8")
    print("cleaned debug")
py_compile.compile(str(p), doraise=True)
print("worker ok")
'''
_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{clean}\nPY", timeout=30)
print(stdout.read().decode(), stderr.read().decode())

c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(10)

test = r'''
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
for i in range(1,11):
    try: req("POST",f"/account/account{i}/stop")
    except: pass
time.sleep(2)
for slot in ["account7"]:
    req("POST", f"/account/{slot}/start?feature=campaign")
print("started account7")
for i in range(30):
    time.sleep(5)
    st = req("GET","/state")
    camp = st["account_states"]["account7"]["campaign"]
    events = [L.get("event") for L in st["account_states"]["account7"].get("logs",[])[-8:]]
    print(f"t+{(i+1)*5}s cycle={camp.get('cycle')} sent={camp.get('success')} fail={camp.get('failed')} status={camp.get('status')} grp={camp.get('current_group','')[:30]} events={events[-4:]}")
    if camp.get("success",0) > 0:
        print("POSTING WORKS")
        break
    if "CYCLE_START" in events and i > 3:
        print("cycle started, waiting for sends...")
'''
_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{test}\nPY", timeout=200)
print("\n=== TEST ===")
print(stdout.read().decode())
print(stderr.read().decode()[:2000])
c.close()
