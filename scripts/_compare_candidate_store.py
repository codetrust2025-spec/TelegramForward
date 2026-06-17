"""Compare VPS vs local candidate_store interview support."""
import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
LOCAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "features", "candidate_store.py")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("wc -l /opt/telegramforward/features/candidate_store.py")
print("VPS", o.read().decode().strip())
_, o, _ = c.exec_command(
    "grep -n '^def interview_\\|^def daily_interview\\|^def pending_works\\|^def set_interview' "
    "/opt/telegramforward/features/candidate_store.py"
)
print("VPS defs:\n", o.read().decode())
c.close()

loc = open(LOCAL, encoding="utf-8").read()
print("local lines", loc.count("\n") + 1)
for fn in [
    "def interview_global_summary",
    "def daily_interview_roster",
    "def pending_works",
    "def set_interview_attendance",
    "def interview_candidate_filter_options",
]:
    print(fn, fn in loc)
