#!/usr/bin/env python3
"""Fix _finalize_cycle_metrics and deploy all campaign posting fixes."""
import base64, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FEATURE_RUNTIME = open(__file__).read().split("FEATURE_RUNTIME = b'''")[1].split("'''")[0] if False else None

FEATURE_RUNTIME_BYTES = b'''"""Proxy views over prefixed AccountState fields (campaign_* / forwarding_*)."""

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
        if name == "should_continue":
            if self._prefix == "campaign_":
                return self._account.should_continue_campaign
            if self._prefix == "forwarding_":
                return self._account.should_continue_forwarding
            return self._account.should_continue
        return getattr(self._account, self._key(name))

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._account, self._key(name), value)


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

PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

# feature_runtime
b64 = base64.b64encode(FEATURE_RUNTIME_BYTES).decode()
c.exec_command(f"echo {b64} | base64 -d > /opt/telegramforward.old/workers/feature_runtime.py", timeout=30)

# fix _finalize_cycle_metrics + remove debug
fix_worker = r'''
import pathlib, py_compile, re
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
src = re.sub(r"\n            try:\n                import traceback\n                with open\(\"/tmp/cycle_err2\.log\".*?\n            except Exception: pass", "", src, flags=re.DOTALL)
old = """    async def _finalize_cycle_metrics(self, groups_total: int, groups_processed: int) -> None:
        from core.cycle_metrics import cycle_metrics_store

        st = self.state
        skipped = (
            st.skipped_already_posted + st.skipped_cooldown + st.skipped_other
        )"""
new = """    async def _finalize_cycle_metrics(self, groups_total: int, groups_processed: int) -> None:
        from core.cycle_metrics import cycle_metrics_store
        from workers.feature_runtime import campaign_runtime

        st = campaign_runtime(self.state)
        skipped = (
            st.skipped_already_posted + st.skipped_cooldown + st.skipped_other
        )"""
if old in src:
    src = src.replace(old, new)
    print("fixed finalize")
else:
    print("finalize already fixed or pattern changed")
p.write_text(src, encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("worker ok")
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{fix_worker}\nPY", timeout=30)
print(stdout.read().decode())

c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(10)

test = r'''
import json, urllib.request, http.cookiejar, time, os
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
for slot in ["account3","account5","account7","account8","account10"]:
    p=f"/opt/telegramforward.old/data/accounts/{slot}/cycle_checkpoint.json"
    if os.path.exists(p): os.remove(p)
time.sleep(2)
for slot in ["account3","account5","account7","account8","account10"]:
    req("POST", f"/account/{slot}/start?feature=campaign")
for slot in ["account1","account2","account4","account6","account9"]:
    req("POST", f"/account/{slot}/start?feature=forwarding")
print("started fleet")
for i in range(24):
    time.sleep(10)
    st = req("GET","/state")
    total = sum(st["account_states"][s]["campaign"]["success"] for s in ["account3","account5","account7","account8","account10"])
    fail = sum(st["account_states"][s]["campaign"]["failed"] for s in ["account3","account5","account7","account8","account10"])
    print(f"t+{(i+1)*10}s campaign sent={total} fail={fail}")
    if total > 0:
        for s in ["account3","account5","account7","account8","account10"]:
            c=st["account_states"][s]["campaign"]
            if c["success"]>0: print(f"  {s}: {c['success']} ok")
        break
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{test}\nPY", timeout=280)
print(stdout.read().decode())
c.close()
