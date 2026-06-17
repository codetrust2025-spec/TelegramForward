#!/usr/bin/env python3
import os, re, sys
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, t=120):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
    _, o, _ = c.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", errors="replace")

js = run("cat /opt/telegramforward.old/static/assets/index-r6ZovQOX.js")
# extract readable UI strings (4+ chars, letters/spaces)
strings = set(re.findall(r'"([A-Za-z][A-Za-z0-9 /&\-]{3,48})"', js))
keywords = [s for s in strings if any(k in s.lower() for k in 
    ['candidate','handler','workspace','demo','tele','dashboard','inbox','crm','payout','expense','salary','fleet','progress','account','payment','smart','reply','tool'])]
for s in sorted(keywords, key=str.lower):
    print(s)

print("\n--- mainView patterns ---")
for m in re.findall(r'mainView===["\'](\w+)["\']|setMainView\(["\'](\w+)["\']', js):
    print(m)

print("\n--- app-view-nav-btn labels nearby ---")
for m in re.finditer(r'app-view-nav-btn[^"]*"[^>]*>([^<]{2,30})', js):
    print(m.group(1))
