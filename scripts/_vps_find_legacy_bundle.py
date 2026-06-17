import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    "ls -la /opt/telegramforward/static/assets/dashboard.bundle.js* 2>/dev/null",
    "grep -c import.meta /opt/telegramforward/static/assets/dashboard.bundle.js 2>/dev/null || echo 0",
    "grep -c import.meta /opt/telegramforward/static/assets/dashboard.bundle.js.trimmed.bak 2>/dev/null || echo 0",
    "for f in /opt/telegramforward/static/assets/dashboard.bundle.js.trimmed.bak /opt/telegramforward/static/assets/dashboard.bundle.js.bak /opt/telegramforward/static/assets/dashboard.bundle.js.orig; do test -f \"$f\" && echo FILE:$f && stat -c %s \"$f\" && grep -c import.meta \"$f\" 2>/dev/null; done",
    "python3 -c \"import pathlib; p=pathlib.Path('/opt/telegramforward/static/assets');\nfor f in sorted(p.glob('*.js'), key=lambda x:-x.stat().st_size)[:15]:\n t=f.read_text('utf-8',errors='replace')[:5000]\n im='import.meta' in t\n daily='Daily ops' in t\n works='Works pending' in t\n if f.stat().st_size>3000000: print(f.name, f.stat().st_size, 'import.meta', im, 'Daily ops', daily, 'Works pending', works)\"",
]
for cmd in cmds:
    print("===", cmd[:80], "===")
    _, o, e = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace")[:3000])
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err[:500])
c.close()
